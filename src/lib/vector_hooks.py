"""
vector_hooks — lifecycle hook registration for automatic vector indexing.

Call init_vector_hooks() once at application startup (from the main app file or
hooks_config.py) to wire up POST_CREATE, POST_UPDATE, and entity-specific
POST_DELETE hooks that keep the vector store in sync with the database.

Example (in hooks_config.py or the project app file):

    from lib.vector_hooks import init_vector_hooks
    from services.vector.impl.ollama_vector import OllamaVectorService
    from api import settings

    if settings.VECTOR_ENABLED == "true":
        _svc = OllamaVectorService(
            base_url=settings.EMBEDDING_BASE_URL,
            model=settings.EMBEDDING_MODEL,
        )
        init_vector_hooks(
            vector_service=_svc,
            entity_to_collection={"Bridge": "bridges", "Equipment": "equipment"},
        )

The entity_to_collection mapping can be built automatically from VectorConfig
(loaded by VectorIndexer) or provided manually.
"""
import logging
from typing import Any, Dict, Optional

from lib.hooks import hooks, HookPoint
from data.vector_indexer import VectorIndexer
from services.vector.vector_service_interface import VectorServiceInterface

logger = logging.getLogger(__name__)

_indexer: Optional[VectorIndexer] = None


def init_vector_hooks(
    vector_service: VectorServiceInterface,
    entity_to_collection: Optional[Dict[str, str]] = None,
    config_path: Optional[str] = None,
    vector_config: Optional[Dict] = None,
) -> VectorIndexer:
    """Initialise the VectorIndexer and register lifecycle hooks.

    Args:
        vector_service:        Concrete service instance (e.g. OllamaVectorService).
        entity_to_collection:  Optional override map {EntityName: collection_name}.
                               If None, the indexer infers this from VectorConfig.
        config_path:           Path to *_vector_config.json (optional).
        vector_config:         Pre-loaded VectorConfig dict (optional).

    Returns:
        The initialised VectorIndexer (can be used directly for search).
    """
    global _indexer

    _indexer = VectorIndexer(
        vector_service=vector_service,
        config_path=config_path,
        vector_config=vector_config,
    )

    # Override entity→collection map if provided explicitly
    if entity_to_collection:
        _indexer._entity_to_collection.update(entity_to_collection)

    # ----------------------------------------------------------------
    # Global POST_CREATE — fires after any entity is created
    # ----------------------------------------------------------------
    @hooks.on(HookPoint.POST_CREATE)
    def _on_create(data: Any) -> Any:
        _index_entity(data, "POST_CREATE")
        return data

    # ----------------------------------------------------------------
    # Global POST_UPDATE — fires after any entity is updated
    # ----------------------------------------------------------------
    @hooks.on(HookPoint.POST_UPDATE)
    def _on_update(data: Any) -> Any:
        _index_entity(data, "POST_UPDATE")
        return data

    # ----------------------------------------------------------------
    # Entity-specific POST_DELETE hooks — one per known collection
    # We register per-entity because POST_DELETE data is just the id
    # (no entity instance), so we need the entity name from the hook key.
    # ----------------------------------------------------------------
    for entity_name, collection in _indexer._entity_to_collection.items():
        _register_delete_hook(entity_name, collection)

    logger.info(
        "Vector hooks initialised for %d entities.",
        len(_indexer._entity_to_collection),
    )
    return _indexer


def get_indexer() -> Optional[VectorIndexer]:
    """Return the active VectorIndexer, or None if not initialised."""
    return _indexer


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _index_entity(data: Any, hook_label: str) -> None:
    """Index a Pydantic entity returned from a hook."""
    if _indexer is None:
        return
    entity_name = type(data).__name__
    try:
        success = _indexer.index_from_entity(entity_name=entity_name, entity=data)
        if success:
            logger.debug("[%s] Indexed %s", hook_label, entity_name)
    except Exception as exc:
        logger.error("[%s] Failed to index %s: %s", hook_label, entity_name, exc)


def _register_delete_hook(entity_name: str, collection: str) -> None:
    """Register a POST_DELETE hook scoped to a single entity."""
    def _on_delete(record_id: Any) -> Any:
        if _indexer:
            try:
                _indexer.remove_record(collection=collection, record_id=str(record_id))
                logger.debug("[POST_DELETE] Removed vector %s/%s", collection, record_id)
            except Exception as exc:
                logger.error("[POST_DELETE] Failed to remove %s/%s: %s", collection, record_id, exc)
        return record_id

    _on_delete.__name__ = f"_vec_delete_{entity_name.lower()}"
    hooks.register(HookPoint.POST_DELETE, _on_delete, entity=entity_name)
