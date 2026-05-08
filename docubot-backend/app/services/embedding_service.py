"""
DocuBot — Servicio de embeddings con OpenAI.
Modelo: text-embedding-3-large (3.072 dimensiones).
Incluye retry con backoff exponencial y procesamiento en batch.
"""
import asyncio
from typing import List
from openai import OpenAI, RateLimitError, APIError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from app.core.config import settings
from app.core.demo_mode import IS_DEMO, demo_embedding


class EmbeddingService:
    """Genera vectores de embeddings para chunks de texto."""

    def __init__(self):
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self._model = settings.OPENAI_MODEL_EMBEDDINGS
        self._dimensions = settings.EMBEDDING_DIMENSIONS  # 3072

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIError)),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=30),
    )
    def _embed_sync(self, texts: List[str]) -> List[List[float]]:
        """Llamada sincrónica al API de OpenAI embeddings."""
        response = self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        # Ordenar por índice para garantizar correspondencia con input
        return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]

    async def embed(self, text: str) -> List[float]:
        if IS_DEMO:
            return demo_embedding(text)
        """Genera embedding de un texto individual."""
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, self._embed_sync, [text])
        return results[0]

    async def embed_batch(
        self, texts: List[str], batch_size: int = 16
    ) -> List[List[float]]:
        """
        Genera embeddings para una lista de textos en batches.
        text-embedding-3-large soporta hasta 2.048 inputs por request,
        pero usamos batches de 16 para evitar timeouts y respetar rate limits.
        """
        all_embeddings: List[List[float]] = []
        loop = asyncio.get_event_loop()

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = await loop.run_in_executor(None, self._embed_sync, batch)
            all_embeddings.extend(embeddings)

            # Pausa breve entre batches para evitar rate limiting
            if i + batch_size < len(texts):
                await asyncio.sleep(0.3)

        return all_embeddings

    async def embed_chunks(self, chunks) -> dict[int, List[float]]:
        """
        Genera embeddings para una lista de Chunk objects.
        Retorna dict {chunk_index: embedding_vector}.
        """
        texts = [c.content for c in chunks]
        embeddings = await self.embed_batch(texts)
        return {chunk.chunk_index: emb for chunk, emb in zip(chunks, embeddings)}


embedding_service = EmbeddingService()
