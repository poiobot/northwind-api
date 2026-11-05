import asyncio
import logging
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class HookPoint(Enum):
    PRE_CREATE = "pre_create"
    POST_CREATE = "post_create"
    PRE_UPDATE = "pre_update"
    POST_UPDATE = "post_update"
    PRE_DELETE = "pre_delete"
    POST_DELETE = "post_delete"
    PRE_FETCH = "pre_fetch"
    POST_FETCH = "post_fetch"


class HookRegistry:
    """Singleton hook registry for entity lifecycle events.

    Hooks are executed in a pipeline pattern: each hook receives data and
    its return value (if not None) replaces the input for the next hook.
    Entity-specific hooks fire before global hooks.

    Usage:
        from lib.hooks import hooks, HookPoint

        @hooks.on(HookPoint.PRE_CREATE, entity="User")
        def hash_password(data):
            if isinstance(data, dict) and "password" in data:
                data["password"] = hash_fn(data["password"])
            return data

        @hooks.on(HookPoint.POST_CREATE)
        def log_creation(data):
            print(f"Created: {data}")
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._hooks: Dict[str, List[Callable]] = {}
        return cls._instance

    def on(self, hook_point: HookPoint, entity: Optional[str] = None):
        """Decorator for hook registration.

        Args:
            hook_point: The lifecycle event to hook into
            entity: Optional entity name to scope the hook (None = global)
        """
        def decorator(func: Callable) -> Callable:
            self.register(hook_point, func, entity)
            return func
        return decorator

    def register(self, hook_point: HookPoint, func: Callable, entity: Optional[str] = None):
        """Register a hook function programmatically.

        Args:
            hook_point: The lifecycle event to hook into
            func: The hook function (receives data, returns modified data or None)
            entity: Optional entity name to scope the hook (None = global)
        """
        key = self._make_key(hook_point, entity)
        if key not in self._hooks:
            self._hooks[key] = []
        self._hooks[key].append(func)

    def execute_sync(self, hook_point: HookPoint, entity_name: str, data: Any = None) -> Any:
        """Execute hooks synchronously in pipeline pattern.

        Entity-specific hooks fire before global hooks. Each hook's return
        value (if not None) replaces the input for the next hook.

        Args:
            hook_point: The lifecycle event
            entity_name: The entity being operated on
            data: The data to pass through the pipeline

        Returns:
            The (possibly modified) data after all hooks have run
        """
        # Entity-specific hooks first
        entity_key = self._make_key(hook_point, entity_name)
        data = self._run_hooks(self._hooks.get(entity_key, []), data)

        # Then global hooks
        global_key = self._make_key(hook_point, None)
        data = self._run_hooks(self._hooks.get(global_key, []), data)

        return data

    async def execute(self, hook_point: HookPoint, entity_name: str, data: Any = None) -> Any:
        """Execute hooks asynchronously in pipeline pattern.

        Supports both sync and async hook functions.

        Args:
            hook_point: The lifecycle event
            entity_name: The entity being operated on
            data: The data to pass through the pipeline

        Returns:
            The (possibly modified) data after all hooks have run
        """
        entity_key = self._make_key(hook_point, entity_name)
        data = await self._run_hooks_async(self._hooks.get(entity_key, []), data)

        global_key = self._make_key(hook_point, None)
        data = await self._run_hooks_async(self._hooks.get(global_key, []), data)

        return data

    def clear(self, hook_point: Optional[HookPoint] = None, entity: Optional[str] = None):
        """Clear registered hooks.

        Args:
            hook_point: If provided, only clear hooks for this point
            entity: If provided, only clear hooks for this entity
        """
        if hook_point is None and entity is None:
            self._hooks.clear()
        else:
            key = self._make_key(hook_point, entity)
            self._hooks.pop(key, None)

    def _make_key(self, hook_point: HookPoint, entity: Optional[str]) -> str:
        if entity:
            return f"{hook_point.value}:{entity}"
        return hook_point.value

    def _run_hooks(self, hook_list: List[Callable], data: Any) -> Any:
        for func in hook_list:
            try:
                result = func(data)
                if result is not None:
                    data = result
            except Exception as e:
                logger.error("Hook %s failed: %s", func.__name__, e, exc_info=True)
        return data

    async def _run_hooks_async(self, hook_list: List[Callable], data: Any) -> Any:
        for func in hook_list:
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(data)
                else:
                    result = func(data)
                if result is not None:
                    data = result
            except Exception as e:
                logger.error("Hook %s failed: %s", func.__name__, e, exc_info=True)
        return data


# Singleton instance
hooks = HookRegistry()
