"""Remote embeddings and generative relevance scoring through LM Studio."""
from concurrent.futures import ThreadPoolExecutor
import math
import os
import threading

import numpy as np
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class RemoteModelError(RuntimeError):
    pass


class ModelClient:
    def __init__(self, base_url, model, session=None):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self._injected = session
        self._clients = threading.local()

    def _session(self):
        if self._injected is not None:
            return self._injected
        if not hasattr(self._clients, 'session'):
            session = requests.Session()
            session.trust_env = False
            if token := os.environ.get('RAG_MODEL_API_KEY') or os.environ.get('LM_STUDIO_API_KEY'):
                session.headers['Authorization'] = 'Bearer ' + token
            for scheme in ('http://', 'https://'):
                session.mount(scheme, HTTPAdapter(max_retries=Retry(total=2, backoff_factor=.5, status_forcelist=[502,503,504], allowed_methods={'POST'})))
            self._clients.session = session
        return self._clients.session

    def request(self, path, payload):
        try:
            response = self._session().post(self.base_url + path, json={'model': self.model, **payload}, timeout=(5, 180))
            response.raise_for_status()
            result = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise RemoteModelError(f'LM Studio request failed for {self.model} ({type(exc).__name__})') from exc
        if not isinstance(result, dict) or result.get('error'):
            raise RemoteModelError(f'LM Studio did not accept the requested operation for {self.model}')
        if result.get('model') and result['model'] != self.model:
            raise RemoteModelError('LM Studio returned a different model than requested')
        return result


class RemoteEncoder(ModelClient):
    device = 'remote'
    max_seq_length = 8192

    def __init__(self, base_url, model, dimensions, instruction, batch_size=8, session=None):
        super().__init__(base_url, model, session)
        self.dimensions = dimensions
        self.instruction = instruction
        self.batch_size = batch_size

    def get_sentence_embedding_dimension(self):
        return self.dimensions

    def encode(self, texts, batch_size=None, interactive=False, **kwargs):
        texts = list(texts)
        if not texts:
            return np.empty((0, self.dimensions), dtype=np.float32)
        result = []
        size = min(batch_size or self.batch_size, self.batch_size)
        for start in range(0, len(texts), size):
            if not interactive:
                from retrieval.workload import wait_for_interactive
                wait_for_interactive()
            batch = texts[start:start + size]
            body = self.request('/embeddings', {'input': batch, 'encoding_format': 'float'})
            items = body.get('data', [])
            if (not isinstance(items, list)
                    or any(not isinstance(item, dict) or type(item.get('index')) is not int for item in items)
                    or sorted(item['index'] for item in items) != list(range(len(batch)))):
                raise RemoteModelError('Embedding response has missing or duplicate input indices')
            try:
                vectors = np.asarray([item['embedding'] for item in sorted(items, key=lambda item: item['index'])], dtype=np.float32)
            except (ValueError, TypeError, KeyError) as exc:
                raise RemoteModelError('Invalid embedding response') from exc
            if vectors.shape != (len(batch), self.dimensions) or not np.isfinite(vectors).all():
                raise RemoteModelError(f'Embedding response must contain {self.dimensions} finite dimensions per input')
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            if not np.isfinite(norms).all() or (norms <= 0).any():
                raise RemoteModelError('Embedding response contains an invalid vector norm')
            result.append(vectors / norms)
        return np.concatenate(result)

    def encode_query(self, query):
        return self.encode([f'Instruct: {self.instruction}\nQuery: {query}'], interactive=True)[0]


class RemoteReranker(ModelClient):
    """Use actual affirmative-token likelihoods, not generated numeric scores.

    LM Studio exposes top-20 chat token probabilities but no /rerank endpoint.
    Sum available case/whitespace variants of the affirmative decision. When
    none are returned for a negative decision, zero is a conservative lower
    bound; preserve the retrieval order for these censored negative ties.
    Scores are ranking signals, not calibrated evidence confidence or the
    reference implementation's yes/(yes+no) probability.
    """
    device = 'remote'

    def score_pair(self, query, passage):
        body = self.request('/chat/completions', {
            'messages': [
                {'role': 'system', 'content': 'Judge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".'},
                {'role': 'user', 'content': f'<Instruct>: Given a scientific research question, retrieve passages that directly answer it.\n<Query>: {query}\n<Document>: {passage}'},
            ],
            'max_tokens': 1, 'reasoning_effort': 'none', 'temperature': 0,
            'logprobs': True, 'top_logprobs': 20, 'stream': False,
        })
        try:
            choice = body['choices'][0]
            decision = choice['message']['content'].strip().lower()
            entry = choice['logprobs']['content'][0]
            top = {item['token']: float(item['logprob']) for item in entry['top_logprobs']}
            top.setdefault(entry['token'], float(entry['logprob']))
        except (TypeError, KeyError, IndexError, ValueError) as exc:
            raise RemoteModelError('The reranker did not return token probabilities') from exc
        if decision not in {'yes', 'no'} or not top or any(not math.isfinite(v) or v > .0001 for v in top.values()):
            raise RemoteModelError('The reranker returned an invalid relevance decision')
        score = sum(math.exp(value) for token, value in top.items() if token.strip().lower() == 'yes')
        if score > 1.0001 or (decision == 'yes' and score == 0):
            raise RemoteModelError('The reranker returned invalid affirmative probabilities')
        return min(score, 1.)

    def predict(self, pairs, **kwargs):
        from retrieval.workload import interactive_request
        with interactive_request(), ThreadPoolExecutor(max_workers=2) as pool:
            return np.asarray(list(pool.map(lambda pair: self.score_pair(*pair), pairs)), dtype=np.float32)
