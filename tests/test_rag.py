import unittest
from types import SimpleNamespace

import numpy as np
from qdrant_client import QdrantClient

from backend.ai_service.rag import DIMENSIONS, KnowledgeChunk, KnowledgeRag


class FakeEmbeddings:
    def create(self, **kwargs):
        return SimpleNamespace(data=[SimpleNamespace(index=i, embedding=[1.0] + [0.0] * (DIMENSIONS - 1))
                                     for i, _ in enumerate(kwargs['input'])])


class FakeSparse:
    def embed(self, texts):
        for text in texts:
            yield SimpleNamespace(indices=np.array([1 if 'baggage' in text else 2]), values=np.array([1.0]))

    def query_embed(self, text):
        return self.embed([text])


class RagTests(unittest.TestCase):
    def setUp(self):
        self.client = QdrantClient(':memory:')
        self.rag = KnowledgeRag(self.client, FakeEmbeddings(), FakeSparse())

    def tearDown(self):
        self.client.close()

    def test_empty_collection_needs_no_models(self):
        rag = KnowledgeRag(self.client)
        self.assertEqual(rag.search('baggage'), [])
        self.assertNotIn('embeddings', rag.__dict__)
        self.assertNotIn('sparse', rag.__dict__)

    def test_repeat_import_and_filtered_hybrid_search_preserve_citations(self):
        chunks = [KnowledgeChunk(source_id=kind, version='v1', chunk_id='1', title=kind,
                                 source_uri='https://example.test/' + kind, kind=kind,
                                 text='baggage rules' if kind == 'legal' else 'refund policy')
                  for kind in ('legal', 'policy')]
        self.rag.ingest(chunks)
        self.rag.ingest(chunks)
        self.assertEqual(self.client.count(self.rag.collection).count, 2)
        hits = self.rag.search('baggage', kind='legal')
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].chunk, chunks[0])

    def test_embedding_failure_propagates(self):
        class Broken:
            def create(self, **kwargs):
                raise RuntimeError('embedding unavailable')
        self.rag._embeddings = Broken()
        with self.assertRaisesRegex(RuntimeError, 'embedding unavailable'):
            self.rag.ingest([KnowledgeChunk(source_id='p', version='1', chunk_id='1',
                            title='Policy', source_uri='fixture:p', kind='policy', text='Refunds')])
        self.assertEqual(self.client.count(self.rag.collection).count, 0)


if __name__ == '__main__':
    unittest.main()
