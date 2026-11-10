"""Remote model validation, ranking failures, and rollback-safe vector staging."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Local_Rag/rag'))
from retrieval.remote import RemoteEncoder, RemoteReranker, RemoteModelError
from retrieval import index_identity
from retrieval import workload
from tools import rebuild_embeddings
from tools import complete_gpu_upgrade


def response(body):
    result = Mock()
    result.json.return_value = body
    return result


class RemoteModelTests(unittest.TestCase):
    def encoder(self, body, dimensions=2):
        session = Mock()
        session.post.return_value = response(body)
        return RemoteEncoder('http://test/v1', 'embedding-test', dimensions, 'Retrieve research passages.', session=session), session

    def test_embedding_order_normalization_and_query_instruction(self):
        model, session = self.encoder({'model':'embedding-test', 'data':[{'index':1,'embedding':[0,2]},{'index':0,'embedding':[3,0]}]})
        np.testing.assert_allclose(model.encode(['first','second']), [[1,0],[0,1]])
        session.post.return_value = response({'model':'embedding-test','data':[{'index':0,'embedding':[1,0]}]})
        model.encode_query('How does salt affect stability?')
        payload = session.post.call_args.kwargs['json']
        self.assertEqual(payload['input'], ['Instruct: Retrieve research passages.\nQuery: How does salt affect stability?'])
        self.assertEqual(payload['model'], 'embedding-test')

    def test_bad_dimensions_zero_vectors_wrong_model_and_duplicate_indices_fail(self):
        bodies = [
            {'model':'other','data':[{'index':0,'embedding':[1,0]}]},
            {'data':[{'index':0,'embedding':[0,0]}]},
            {'data':[{'index':0,'embedding':[1,0,0]}]},
            {'data':[{'index':0,'embedding':[float('nan'),1]}]},
            {'data':[{'index':'0','embedding':[1,0]}]},
            {'data':['malformed']},
            {'data':[{'index':0,'embedding':[1,0]},{'index':0,'embedding':[0,1]}]},
            {'error':'unsupported operation'},
        ]
        for body in bodies:
            with self.subTest(body=body), self.assertRaises(RemoteModelError):
                self.encoder(body)[0].encode(['text'])

    def test_empty_input_does_not_make_network_request(self):
        model, session = self.encoder({})
        self.assertEqual(model.encode([]).shape, (0,2))
        session.post.assert_not_called()

    def test_reranker_uses_real_affirmative_probabilities(self):
        session = Mock()
        session.post.return_value = response({'model':'rank-test','choices':[{
            'message':{'content':'yes'}, 'logprobs':{'content':[{'token':'yes','logprob':np.log(.7),
            'top_logprobs':[{'token':'yes','logprob':np.log(.7)},{'token':'Yes','logprob':np.log(.1)}]}]}}]})
        ranker = RemoteReranker('http://test/v1','rank-test',session=session)
        self.assertAlmostEqual(ranker.score_pair('Question','Passage'), .8)
        payload = session.post.call_args.kwargs['json']
        self.assertTrue(payload['logprobs'])
        self.assertEqual(payload['max_tokens'], 1)
        self.assertIn('<Document>: Passage',payload['messages'][1]['content'])

    def test_censored_negative_scores_are_lower_bounds_not_fabricated_yes_logits(self):
        session = Mock()
        session.post.return_value = response({'choices':[{'message':{'content':'no'},'logprobs':{'content':[{
            'token':'no','logprob':-.01,'top_logprobs':[{'token':'no','logprob':-.01}]}]}}]})
        ranker = RemoteReranker('http://test/v1','rank-test',session=session)
        self.assertEqual(ranker.score_pair('Question','Unrelated passage'),0)

    def test_missing_probabilities_or_wrong_model_are_errors(self):
        for body in [{'choices':[{'message':{'content':'yes'},'logprobs':None}]}, {'model':'other','choices':[]}]:
            session = Mock();session.post.return_value=response(body)
            with self.subTest(body=body), self.assertRaises(RemoteModelError):
                RemoteReranker('http://test/v1','rank-test',session=session).score_pair('Q','D')


class WorkloadTests(unittest.TestCase):
    def test_overlapping_queries_hold_priority_until_both_finish(self):
        with tempfile.TemporaryDirectory() as root, patch.dict('os.environ', {'RAG_EMBED_MIGRATION_STATUS':str(Path(root)/'status.json')}):
            self.assertFalse(workload.interactive_active())
            with workload.interactive_request():
                with workload.interactive_request():
                    self.assertTrue(workload.interactive_active())
                self.assertTrue(workload.interactive_active())
            self.assertFalse(workload.interactive_active())

    def test_abandoned_query_marker_does_not_block_indexing(self):
        with tempfile.TemporaryDirectory() as root, patch.dict('os.environ', {'RAG_EMBED_MIGRATION_STATUS':str(Path(root)/'status.json')}):
            directory = workload.activity_directory()
            directory.mkdir()
            marker = directory / 'abandoned.lease'
            marker.touch()
            self.assertFalse(workload.interactive_active())
            self.assertFalse(marker.exists())


class VectorMigrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root/'rag.sqlite'
        self.stage = self.root/'migration/vectors.sqlite'
        conn = rebuild_embeddings.open_index(self.source)
        conn.executescript('''CREATE TABLE papers(paper_id TEXT PRIMARY KEY,title TEXT);
            CREATE TABLE chunks(chunk_id TEXT PRIMARY KEY,paper_id TEXT,text TEXT,section_name TEXT);
            CREATE VIRTUAL TABLE chunks_vec USING vec0(chunk_id TEXT PRIMARY KEY,embedding FLOAT[3]);
            INSERT INTO papers VALUES('p','Real title');
            INSERT INTO chunks VALUES('c','p','Original source passage','Methods');''')
        conn.execute('INSERT INTO chunks_vec VALUES(?,?)',('c',np.array([1,0,0],dtype=np.float32).tobytes()))
        conn.commit();conn.close()
        self.profile={'provider':'lmstudio','model':'new-model','dimensions':2,'revision':'Q8_0'}
        patcher=patch.object(rebuild_embeddings,'profile',return_value=self.profile)
        patcher.start();self.addCleanup(patcher.stop)
        self.model=Mock()
        self.model.encode.return_value=np.array([[0,1]],dtype=np.float32)

    def build(self):
        return rebuild_embeddings.stage(self.source,self.stage,encoder=self.model)

    def test_staging_is_resumable_and_does_not_touch_original_vectors(self):
        self.assertEqual(self.build(),1)
        self.assertEqual(self.build(),0)
        self.assertEqual(self.model.encode.call_count,1)
        conn=rebuild_embeddings.open_index(self.source)
        self.addCleanup(conn.close)
        self.assertIn('FLOAT[3]',conn.execute("SELECT sql FROM sqlite_master WHERE name='chunks_vec'").fetchone()[0])
        self.assertEqual(conn.execute('SELECT text FROM chunks').fetchone()[0],'Original source passage')

    def test_activation_preserves_source_metadata_and_creates_rollback_backup(self):
        self.build()
        backup=rebuild_embeddings.activate(self.source,self.stage)
        conn=rebuild_embeddings.open_index(self.source)
        self.addCleanup(conn.close)
        self.assertIn('FLOAT[2]',conn.execute("SELECT sql FROM sqlite_master WHERE name='chunks_vec'").fetchone()[0])
        self.assertEqual(index_identity.read_profile(conn),self.profile)
        self.assertEqual(conn.execute('SELECT title FROM papers').fetchone()[0],'Real title')
        old=rebuild_embeddings.open_index(backup)
        self.addCleanup(old.close)
        self.assertIn('FLOAT[3]',old.execute("SELECT sql FROM sqlite_master WHERE name='chunks_vec'").fetchone()[0])

    def test_failed_service_health_restores_live_index_memory_and_config(self):
        self.build()
        config = self.root / 'labui.env'
        config.write_bytes(b'RAG_EMBED_MODEL=original-model\nOTHER_SETTING=preserved\n')
        memory = self.root / 'memory.db'
        with sqlite3.connect(memory) as conn:
            conn.execute('CREATE TABLE memories(content TEXT)')
            conn.execute("INSERT INTO memories VALUES('Saved conversation')")
        def unhealthy(*_):
            with sqlite3.connect(memory) as conn:
                conn.execute("UPDATE memories SET content='Changed during startup'")
            raise RuntimeError('Health check failed')
        with patch.object(complete_gpu_upgrade, 'stage'), \
                patch.object(complete_gpu_upgrade, 'is_active', return_value=True), \
                patch.object(complete_gpu_upgrade, 'service') as controls, \
                patch.object(complete_gpu_upgrade, 'target_config', return_value=b'RAG_EMBED_MODEL=new-model\n'), \
                patch.object(complete_gpu_upgrade, 'wait_ready', side_effect=unhealthy):
            with self.assertRaisesRegex(RuntimeError, 'Health check failed'):
                complete_gpu_upgrade.promote(self.source, self.stage, config, 'http://test')
        conn = rebuild_embeddings.open_index(self.source)
        self.addCleanup(conn.close)
        self.assertIn('FLOAT[3]', conn.execute("SELECT sql FROM sqlite_master WHERE name='chunks_vec'").fetchone()[0])
        self.assertEqual(config.read_bytes(), b'RAG_EMBED_MODEL=original-model\nOTHER_SETTING=preserved\n')
        with sqlite3.connect(memory) as conn:
            self.assertEqual(conn.execute('SELECT content FROM memories').fetchone()[0], 'Saved conversation')
        self.assertEqual(controls.call_args.args, ('start', 'labui-library-import.service'))
        self.assertEqual(json.loads((self.stage.parent / 'cutover.json').read_text())['phase'], 'rolled_back')

    def test_successful_service_cutover_keeps_target_and_resumes_import(self):
        self.build()
        config = self.root / 'labui.env'
        config.write_bytes(b'RAG_EMBED_MODEL=original-model\n')
        with patch.object(complete_gpu_upgrade, 'stage'), \
                patch.object(complete_gpu_upgrade, 'is_active', return_value=True), \
                patch.object(complete_gpu_upgrade, 'service') as controls, \
                patch.object(complete_gpu_upgrade, 'target_config', return_value=b'RAG_EMBED_MODEL=new-model\n'), \
                patch.object(complete_gpu_upgrade, 'validate_search'), \
                patch.object(complete_gpu_upgrade, 'wait_ready', return_value={'papers':1,'chunks':1}):
            complete_gpu_upgrade.promote(self.source, self.stage, config, 'http://test')
        self.assertEqual(config.read_bytes(), b'RAG_EMBED_MODEL=new-model\n')
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(controls.call_args.args, ('start', 'labui-library-import.service'))
        self.assertEqual(json.loads((self.stage.parent / 'cutover.json').read_text())['phase'], 'active')

    def test_process_restart_recovers_interrupted_cutover(self):
        config = self.root / 'labui.env'
        config.write_bytes(b'Broken configuration')
        backup = self.root / 'backup'
        backup.mkdir()
        (backup / 'labui.env').write_bytes(b'Original configuration')
        complete_gpu_upgrade.snapshot(self.source, backup / 'rag.db')
        self.build()
        rebuild_embeddings.activate(self.source, self.stage)
        complete_gpu_upgrade.save_state(self.stage, phase='cutover', backup_dir=str(backup), importer_running=True)
        with patch.object(complete_gpu_upgrade, 'service') as controls:
            complete_gpu_upgrade.recover_interrupted(self.source, self.stage, config)
        conn = rebuild_embeddings.open_index(self.source)
        self.addCleanup(conn.close)
        self.assertIn('FLOAT[3]', conn.execute("SELECT sql FROM sqlite_master WHERE name='chunks_vec'").fetchone()[0])
        self.assertEqual(config.read_bytes(), b'Original configuration')
        self.assertEqual(controls.call_args.args, ('start', 'labui-library-import.service'))

    def test_live_cutover_search_rejects_empty_or_out_of_scope_results(self):
        for results in ([], [{'paper_id':'another-paper'}]):
            with self.subTest(results=results), patch.object(complete_gpu_upgrade.requests, 'Session') as factory:
                factory.return_value.post.return_value = response({'results':results})
                with self.assertRaisesRegex(RuntimeError, 'scope check'):
                    complete_gpu_upgrade.validate_search(self.source, 'http://test')
                self.assertEqual(factory.return_value.post.call_args.kwargs['json']['selected_paper_ids'], ['p'])

    def test_source_changes_prevent_activation_before_any_live_vector_change(self):
        self.build()
        with sqlite3.connect(self.source) as conn:
            conn.execute("UPDATE chunks SET text='Source updated while importing'")
        with self.assertRaisesRegex(ValueError,'library changed'):
            rebuild_embeddings.activate(self.source,self.stage)
        conn=rebuild_embeddings.open_index(self.source);self.addCleanup(conn.close)
        self.assertIn('FLOAT[3]',conn.execute("SELECT sql FROM sqlite_master WHERE name='chunks_vec'").fetchone()[0])
        self.assertEqual(conn.execute('SELECT count(*) FROM chunks_vec').fetchone()[0],1)

    def test_same_dimension_different_model_cannot_query_the_index(self):
        with sqlite3.connect(self.source) as conn:
            index_identity.write_profile(conn,{'provider':'local','model':'old-model','dimensions':3})
        conn=rebuild_embeddings.open_index(self.source);self.addCleanup(conn.close)
        with patch.object(index_identity,'profile',return_value={'provider':'local','model':'other-model','dimensions':3}):
            with self.assertRaisesRegex(ValueError,'identity'):
                index_identity.ensure_compatible(conn)

    def test_failed_copy_rolls_back_virtual_table_replacement(self):
        self.build()
        with sqlite3.connect(self.stage) as conn:
            conn.execute('UPDATE staged_vectors SET embedding=?', (np.array([float('nan'),1],dtype=np.float32).tobytes(),))
        with self.assertRaisesRegex(ValueError,'rolled back'):
            rebuild_embeddings.activate(self.source,self.stage)
        conn=rebuild_embeddings.open_index(self.source);self.addCleanup(conn.close)
        self.assertIn('FLOAT[3]',conn.execute("SELECT sql FROM sqlite_master WHERE name='chunks_vec'").fetchone()[0])
        self.assertEqual(conn.execute('SELECT count(*) FROM chunks_vec').fetchone()[0],1)


class GraphRetrievalTests(unittest.TestCase):
    def test_graph_candidates_respect_selected_papers(self):
        from retrieval import graph, search
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'graph.sqlite'
            with patch.object(graph,'GRAPH_DB_PATH',path):
                graph.init_graph_db()
                conn=graph._open_db()
                entity=graph.upsert_entity(conn,'NaCl','Chemical','','p1')
                graph.link_entity_chunk(conn,entity,'selected','p1')
                graph.link_entity_chunk(conn,entity,'outside','p2')
                conn.commit();conn.close()
                source=sqlite3.connect(':memory:')
                self.addCleanup(source.close)
                source.execute('CREATE TABLE chunks(chunk_id TEXT,paper_id TEXT)')
                source.executemany('INSERT INTO chunks VALUES(?,?)',[('selected','p1'),('outside','p2')])
                found=search._graph_search(source,'How does NaCl affect stability?',20,['p1'])
                self.assertEqual(found,['selected'])

    def test_graph_passages_go_through_the_final_reranker(self):
        from retrieval import search
        conn=Mock()
        ranker=Mock();ranker.predict.return_value=np.array([.9])
        chunk={'chunk_id':'graph','paper_id':'p','title':'Paper','text':'A graph-linked source passage'}
        with patch.object(search,'_open_db',return_value=conn), \
             patch.object(search,'_title_search',return_value=[]), \
             patch.object(search,'_bm25_search',return_value=[]), \
             patch.object(search,'_dense_search',return_value=[]), \
             patch.object(search,'_graph_search',return_value=['graph']), \
             patch.object(search,'_fetch_chunks',return_value=[chunk]):
            result=search.search('Question',np.array([1,0]),ranker)
        self.assertEqual(result,[chunk])
        self.assertIn('graph-linked',ranker.predict.call_args.args[0][0][1])


if __name__=='__main__':unittest.main()
