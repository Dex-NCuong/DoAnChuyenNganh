import asyncio
from datetime import datetime
from typing import Iterable, List, Sequence

import numpy as np
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..core.config import settings
from ..core.database import create_or_load_faiss_index, save_faiss_index
from ..models.document import mark_document_embedded, mark_chunks_embedded


class EmbeddingService:
    """Service to generate embeddings via OpenAI or local SentenceTransformers."""

    _local_model = None

    def __init__(self, provider: str | None = None, model: str | None = None):
        self.provider = (provider or settings.embedding_provider).lower()
        self.model = model or settings.embedding_model
        self.batch_size = settings.embedding_batch_size
        self._openai_client = None

        if self.provider == "openai" and settings.openai_api_key:
            from openai import OpenAI

            self._openai_client = OpenAI(api_key=settings.openai_api_key)
        elif self.provider != "openai":
            # Force local provider if OpenAI key is missing
            self.provider = "local"
            self.model = settings.embedding_local_model
        elif not settings.openai_api_key:
            # fallback to local if provider openai but no key
            self.provider = "local"
            self.model = settings.embedding_local_model

    async def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        cleaned = [t.strip() for t in texts if t and t.strip()]
        if not cleaned:
            return []

        if self.provider == "openai" and self._openai_client:
            return await self._embed_openai(cleaned)
        return await self._embed_local(cleaned)

    async def _embed_openai(self, texts: Sequence[str]) -> List[List[float]]:
        async def _call(batch: Sequence[str]):
            return await asyncio.to_thread(
                self._openai_client.embeddings.create,
                model=self.model,
                input=list(batch),
            )

        embeddings: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            response = await _call(batch)
            embeddings.extend([item.embedding for item in response.data])
        return embeddings

    async def _embed_local(self, texts: Sequence[str]) -> List[List[float]]:
        def _get_model():
            from sentence_transformers import SentenceTransformer

            if EmbeddingService._local_model is None:
                EmbeddingService._local_model = SentenceTransformer(self.model)
            return EmbeddingService._local_model

        model = await asyncio.to_thread(_get_model)

        def _encode(batch: Iterable[str]):
            return model.encode(list(batch), normalize_embeddings=True).tolist()

        embeddings: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            vectors = await asyncio.to_thread(_encode, batch)
            embeddings.extend(vectors)
        return embeddings

    async def embed_document_chunks(
        self,
        db: AsyncIOMotorDatabase,
        user_id: str,
        document,
        chunks: Sequence[dict],
    ) -> None:
        """Generate embeddings for provided chunks and store in FAISS and MongoDB."""

        texts = [chunk.get("content", "").strip() for chunk in chunks]
        embeddings = await self.embed_texts(texts)

        if not embeddings:
            # Nothing to embed, but still mark document as embedded with zero vectors
            await mark_document_embedded(db, document.id, self.model, 0)
            return

        vectors = np.array(embeddings, dtype="float32")
        dimension = vectors.shape[1]

        namespace = getattr(document, "faiss_namespace", None) or f"user_{user_id}_doc_{getattr(document, 'id', '')}"
        index = create_or_load_faiss_index(dimension=dimension, namespace=namespace)

        # Use existing total as base offset, ids sequential from ntotal
        start_position = int(index.ntotal)
        ids = np.arange(start_position, start_position + len(vectors), dtype="int64")

        # Add vectors to FAISS index (supports IDs)
        index.add_with_ids(vectors, ids)
        save_faiss_index(index, namespace=namespace)

        now = datetime.utcnow()
        embedding_records = []
        chunk_updates = []

        for chunk, vector_id in zip(chunks, ids.tolist()):
            chunk_id = chunk.get("_id")
            embedding_records.append(
                {
                    "user_id": user_id,
                    "document_id": document.id,
                    "chunk_id": chunk_id,
                    "chunk_index": chunk.get("chunk_index"),
                    "vector_index": vector_id,
                    "embedding_model": self.model,
                    "provider": self.provider,
                    "created_at": now,
                }
            )
            chunk_updates.append(
                {
                    "chunk_id": chunk_id,
                    "embedding_index": vector_id,
                    "embedding_model": self.model,
                }
            )

        if embedding_records:
            await db["embeddings"].insert_many(embedding_records)

        if chunk_updates:
            await mark_chunks_embedded(db, chunk_updates)

        await mark_document_embedded(db, document.id, self.model, dimension)

