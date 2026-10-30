"""Synchronous hybrid retrieval of curated legal and policy text chunks.

Independent of case processing; failures propagate to the caller.
"""
import argparse
import json
import os
from functools import cached_property
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from dotenv import dotenv_values
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field
from qdrant_client import QdrantClient, models

from .settings import ROOT

EMBEDDING_MODEL = 'text-embedding-3-small'
DIMENSIONS = 1536


class LegalProvenance(BaseModel):
    page: int = Field(ge=1)
    pdf_sha256: str
    source_kind: str
    approval_status: str
    runtime_enabled: bool = False
    language: str


class KnowledgeChunk(BaseModel):
    """One curated passage; stable source/version/chunk IDs enable repeat imports."""
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    source_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_uri: str = Field(min_length=1)
    kind: Literal['legal', 'policy']
    text: str = Field(min_length=1, max_length=6000)
    provenance: LegalProvenance | None = None


class SearchHit(BaseModel):
    score: float
    chunk: KnowledgeChunk


class KnowledgeRag:
    def __init__(self, client=None, embeddings=None, sparse=None, collection=None):
        self.env = {**dotenv_values(ROOT / '.env'), **os.environ}
        self.collection = collection or self.env.get('QDRANT_COLLECTION') or 'legal_policies'
        self.client = client if client is not None else QdrantClient(
            url=self.env.get('QDRANT_URL') or 'http://127.0.0.1:6335',
            api_key=self.env.get('QDRANT_API_KEY') or None, timeout=30,
        )
        self._embeddings = embeddings
        self._sparse = sparse

    @cached_property
    def embeddings(self):
        if self._embeddings is not None:
            return self._embeddings
        key = self.env.get('OPENAI_API_KEY')
        if not key:
            raise ValueError('OPENAI_API_KEY is required for non-empty RAG ingestion/search')
        return OpenAI(api_key=key, timeout=60, max_retries=0).embeddings

    @cached_property
    def sparse(self):
        if self._sparse is not None:
            return self._sparse
        from fastembed import SparseTextEmbedding
        return SparseTextEmbedding(model_name='Qdrant/bm25')

    def initialize(self):
        """Create an empty collection or validate it without deleting existing data."""
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                self.collection,
                vectors_config={'dense': models.VectorParams(
                    size=DIMENSIONS, distance=models.Distance.COSINE)},
                sparse_vectors_config={'bm25': models.SparseVectorParams(
                    modifier=models.Modifier.IDF)},
            )
        params = self.client.get_collection(self.collection).config.params
        dense = params.vectors.get('dense') if isinstance(params.vectors, dict) else None
        sparse = (params.sparse_vectors or {}).get('bm25')
        if (dense is None or dense.size != DIMENSIONS
                or dense.distance != models.Distance.COSINE
                or sparse is None or sparse.modifier != models.Modifier.IDF):
            raise ValueError('Incompatible RAG collection; use a separate collection name')

    def _dense(self, texts):
        response = self.embeddings.create(model=EMBEDDING_MODEL, input=texts,
                                          dimensions=DIMENSIONS)
        return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]

    @staticmethod
    def _sparse_vector(vector):
        return models.SparseVector(indices=vector.indices.tolist(), values=vector.values.tolist())

    def ingest(self, chunks: list[KnowledgeChunk]):
        """Upsert pre-chunked passages in bounded batches. Partial batches may persist on failure."""
        self.initialize()
        for start in range(0, len(chunks), 32):
            batch = chunks[start:start + 32]
            texts = [chunk.text for chunk in batch]
            dense = self._dense(texts)
            sparse = list(self.sparse.embed(texts))
            points = []
            for chunk, vector, keywords in zip(batch, dense, sparse, strict=True):
                identity = json.dumps([chunk.source_id, chunk.version, chunk.chunk_id])
                points.append(models.PointStruct(
                    id=str(uuid5(NAMESPACE_URL, identity)),
                    vector={'dense': vector, 'bm25': self._sparse_vector(keywords)},
                    payload=chunk.model_dump(),
                ))
            self.client.upsert(self.collection, points=points, wait=True)
        return len(chunks)

    def search(self, query: str, limit: int = 5, kind: Literal['legal', 'policy'] | None = None):
        if not query.strip() or len(query) > 6000 or not 1 <= limit <= 100:
            raise ValueError('Provide a query of 1–6000 characters and a limit of 1–100')
        if kind not in (None, 'legal', 'policy'):
            raise ValueError('kind must be legal or policy')
        self.initialize()
        if self.client.count(self.collection, exact=True).count == 0:
            return []
        dense = self._dense([query])[0]
        sparse = self._sparse_vector(next(iter(self.sparse.query_embed(query))))
        restriction = models.Filter(must=[models.FieldCondition(
            key='kind', match=models.MatchValue(value=kind))]) if kind else None
        results = self.client.query_points(
            self.collection,
            prefetch=[
                models.Prefetch(query=dense, using='dense', limit=max(20, limit), filter=restriction),
                models.Prefetch(query=sparse, using='bm25', limit=max(20, limit), filter=restriction),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit, with_payload=True,
        )
        return [SearchHit(score=hit.score, chunk=KnowledgeChunk.model_validate(hit.payload))
                for hit in results.points]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    sub.add_parser('status')
    ingest = sub.add_parser('ingest')
    ingest.add_argument('jsonl', type=Path)
    search = sub.add_parser('search')
    search.add_argument('query')
    search.add_argument('--limit', type=int, default=5)
    search.add_argument('--kind', choices=['legal', 'policy'])
    args = parser.parse_args()
    rag = KnowledgeRag()
    try:
        if args.command in ('init', 'status'):
            if args.command == 'init':
                rag.initialize()
            print(json.dumps({'collection': rag.collection,
                              'points': rag.client.count(rag.collection, exact=True).count}))
        elif args.command == 'ingest':
            chunks = [KnowledgeChunk.model_validate_json(line)
                      for line in args.jsonl.read_text().splitlines() if line.strip()]
            print(json.dumps({'upserted': rag.ingest(chunks)}))
        else:
            print(json.dumps([hit.model_dump() for hit in rag.search(
                args.query, args.limit, args.kind)], indent=2))
    finally:
        rag.client.close()


if __name__ == '__main__':
    main()
