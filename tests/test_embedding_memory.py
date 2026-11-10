"""Alternate embedding models must work for long chunks and existing memory."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Local_Rag" / "rag"))
from retrieval import embed
import memory


class EmbeddingTests(unittest.TestCase):
    def test_small_model_keeps_its_positional_limit(self):
        model = Mock(max_seq_length=512)
        model.get_sentence_embedding_dimension.return_value = 384
        with patch("sentence_transformers.SentenceTransformer", return_value=model), patch.object(embed, "EMBED_DIM", 384):
            _, result = embed.load_embed_model()
        self.assertEqual(result.max_seq_length, 512)

    def test_wrong_embedding_dimension_fails_before_indexing(self):
        model = Mock(max_seq_length=512)
        model.get_sentence_embedding_dimension.return_value = 384
        with patch("sentence_transformers.SentenceTransformer", return_value=model), patch.object(embed, "EMBED_DIM", 1024):
            with self.assertRaisesRegex(ValueError, "produces 384 dimensions"):
                embed.load_embed_model()

    def test_empty_embeddings_follow_configured_dimension(self):
        with patch.object(embed, "EMBED_DIM", 384):
            self.assertEqual(embed.embed_texts(None, None, []).shape, (0, 384))


class MemoryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        for target, attribute, value in [(memory, "MEMORY_DB_PATH", Path(directory.name)/"memory.db"),
                                         (memory, "EMBED_DIM", 4), (embed, "EMBED_DIM", 4)]:
            mock = patch.object(target, attribute, value)
            mock.start()
            self.addCleanup(mock.stop)
        memory.init_db()

    def connection(self):
        conn = memory._open_db()
        self.addCleanup(conn.close)
        return conn

    def test_dense_memory_recall_works_without_a_keyword_match(self):
        vector = np.array([1, 0, 0, 0], dtype=np.float32)
        mid = memory.save_memory("A stored finding", vector)
        results = memory.search_memories(vector, "unrelated_keyword")
        self.assertEqual(results[0]["memory_id"], mid)
        self.assertEqual(self.connection().execute("SELECT COUNT(*) FROM memories_vec").fetchone()[0], 1)

    def old_index(self):
        conn = self.connection()
        conn.execute("DROP TABLE memories_vec")
        conn.execute("CREATE VIRTUAL TABLE memories_vec USING vec0(memory_id TEXT, embedding FLOAT[8])")
        conn.commit()
        mid = memory.save_memory("A preserved finding", np.ones(8, dtype=np.float32))
        session = memory.create_session("Preserved conversation")
        memory.add_turn(session, "user", "Original question")
        return mid, session

    def test_dimension_repair_preserves_text_and_conversation(self):
        mid, session = self.old_index()
        model = Mock()
        model.encode.return_value = np.ones((1, 4), dtype=np.float32)
        self.assertEqual(memory.repair_vector_index(None, model), 1)
        self.assertEqual(memory.get_session(session)["turns"][0]["content"], "Original question")
        self.assertEqual(memory.get_all_memories()[0]["memory_id"], mid)
        self.assertEqual(memory.search_memories(np.ones(4, dtype=np.float32), "unrelated")[0]["memory_id"], mid)

    def test_failed_embedding_leaves_original_vectors_intact(self):
        self.old_index()
        model = Mock()
        model.encode.side_effect = RuntimeError("encoder failed")
        with self.assertRaisesRegex(RuntimeError, "encoder failed"):
            memory.repair_vector_index(None, model)
        sql = self.connection().execute("SELECT sql FROM sqlite_master WHERE name='memories_vec'").fetchone()[0]
        self.assertIn("FLOAT[8]", sql)
        self.assertEqual(self.connection().execute("SELECT COUNT(*) FROM memories_vec").fetchone()[0], 1)

    def test_repair_backfills_previously_missing_vectors(self):
        mid = memory.save_memory("Text survived an old dimension mismatch", np.ones(8, dtype=np.float32))
        model = Mock()
        model.encode.return_value = np.ones((1, 4), dtype=np.float32)
        self.assertEqual(memory.repair_vector_index(None, model), 1)
        self.assertEqual(memory.search_memories(np.ones(4, dtype=np.float32), "unrelated")[0]["memory_id"], mid)
        self.assertEqual(memory.repair_vector_index(None, model), 0)


if __name__ == "__main__":
    unittest.main()
