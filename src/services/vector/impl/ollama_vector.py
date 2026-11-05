"""
OllamaVectorService — vector embedding + in-memory search backed by Ollama.

Embeddings are generated via Ollama's OpenAI-compatible /v1/embeddings endpoint.
Vectors are stored in-process (in-memory) with cosine similarity search using numpy.

This implementation is intentionally simple and swap-friendly:
- Replace with MongoDBAtlasVector, QdrantVector, etc. without changing VectorIndexer.
- The interface is defined in services/vector/vector_service_interface.py.

Configuration (via api/settings.py → .env):
    EMBEDDING_BASE_URL  = http://localhost:11434/v1
    EMBEDDING_MODEL     = nomic-embed-text
    EMBEDDING_API_KEY   = ollama
"""
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

import numpy as np
from openai import OpenAI

from services.vector.vector_service_interface import VectorServiceInterface

logger = logging.getLogger(__name__)


class OllamaVectorService(VectorServiceInterface):
    """Ollama-backed embedding service with in-memory cosine-similarity search.

    The in-memory store is suitable for development and small datasets.
    Replace with a persistent backend (Atlas, Qdrant, pgvector) for production.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "nomic-embed-text",
        api_key: str = "ollama",
        timeout: int = 60,
    ):
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        # Structure: {collection: {id: {"vector": np.ndarray, "aliases": [...], "text": "..."}}}
        self._store: Dict[str, Dict[str, Dict]] = defaultdict(dict)

    # ------------------------------------------------------------------
    # VectorServiceInterface implementation
    # ------------------------------------------------------------------

    def embed(self, text: str) -> List[float]:
        """Call Ollama embeddings API and return the embedding vector."""
        try:
            response = self.client.embeddings.create(model=self.model, input=text)
            return response.data[0].embedding
        except Exception as exc:
            logger.error("Embedding failed: %s", exc)
            raise

    def upsert(self, id: str, collection: str, aliases: List[str], text: str) -> bool:
        """Embed text and store/replace the vector for this record."""
        try:
            vector = np.array(self.embed(text), dtype=np.float32)
            # Normalise for cosine similarity via dot product
            norm = np.linalg.norm(vector)
            if norm > 0:
                vector = vector / norm
            self._store[collection][id] = {
                "vector": vector,
                "aliases": aliases,
                "text": text,
            }
            logger.debug("Upserted vector for %s/%s", collection, id)
            return True
        except Exception as exc:
            logger.error("Upsert failed for %s/%s: %s", collection, id, exc)
            return False

    def search(
        self,
        query_text: str,
        collection: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return the top-k most similar records to query_text."""
        try:
            qvec = np.array(self.embed(query_text), dtype=np.float32)
            norm = np.linalg.norm(qvec)
            if norm > 0:
                qvec = qvec / norm
        except Exception as exc:
            logger.error("Query embedding failed: %s", exc)
            return []

        collections_to_search = (
            [collection] if collection and collection in self._store
            else list(self._store.keys())
        )

        scored: List[Dict[str, Any]] = []
        for coll in collections_to_search:
            for record_id, payload in self._store[coll].items():
                score = float(np.dot(qvec, payload["vector"]))
                scored.append({
                    "id": record_id,
                    "collection": coll,
                    "aliases": payload["aliases"],
                    "text": payload["text"],
                    "score": score,
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def delete(self, id: str, collection: str) -> bool:
        """Remove a vector from the in-memory store."""
        if collection in self._store and id in self._store[collection]:
            del self._store[collection][id]
            logger.debug("Deleted vector for %s/%s", collection, id)
            return True
        return False

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def collection_count(self, collection: str) -> int:
        """Return the number of vectors stored for a collection."""
        return len(self._store.get(collection, {}))

    def total_count(self) -> int:
        """Return the total number of vectors across all collections."""
        return sum(len(v) for v in self._store.values())
