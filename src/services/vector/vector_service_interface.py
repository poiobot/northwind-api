"""
VectorServiceInterface — abstract contract for vector embedding + search services.

Mirrors the pattern of DAOInterface / IDatabaseService in services/database/.
Concrete implementations live in impl/ (e.g. ollama_vector.py).
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class VectorServiceInterface(ABC):
    """Abstract interface for storing and searching vector embeddings."""

    @abstractmethod
    def upsert(
        self,
        id: str,
        collection: str,
        aliases: List[str],
        text: str,
    ) -> bool:
        """Embed *text* and store/update the vector for the given record.

        Args:
            id:         The record's primary identifier (e.g. MongoDB _id as str).
            collection: The source collection/table name (e.g. "bridges").
            aliases:    Human-readable names for this record (for display in results).
            text:       The composite text to embed (built from alias + semantic fields).

        Returns:
            True if the operation succeeded.
        """

    @abstractmethod
    def search(
        self,
        query_text: str,
        collection: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Embed *query_text* and return the closest vectors.

        Args:
            query_text: Natural-language query string.
            collection: If provided, restrict results to this collection.
            limit:      Maximum number of results to return.

        Returns:
            List of result dicts, each containing at minimum:
                {id, collection, aliases, text, score}
            Sorted by descending similarity score.
        """

    @abstractmethod
    def delete(self, id: str, collection: str) -> bool:
        """Remove the vector for a given record.

        Args:
            id:         Record primary identifier.
            collection: Collection name.

        Returns:
            True if a vector was found and removed.
        """

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Return a raw embedding vector for *text* (useful for batch operations)."""
