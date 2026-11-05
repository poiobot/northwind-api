"""
Hooks configuration file.

Register custom hooks for entity lifecycle events. This file is NOT overwritten
by code regeneration, so your customizations are safe.

Example usage:

    from lib.hooks import hooks, HookPoint

    @hooks.on(HookPoint.PRE_CREATE, entity="User")
    def hash_user_password(data):
        # Hash password before saving
        if isinstance(data, dict) and "password" in data:
            from services.authorisation.authorisation_handler import AuthorisationHandler
            auth = AuthorisationHandler()
            data["password"] = auth.get_password_hash(data["password"])
        return data

    @hooks.on(HookPoint.POST_CREATE)
    def log_creation(data):
        # Log all entity creations
        import logging
        logging.getLogger("hooks").info("Entity created: %s", type(data).__name__)

Available hook points:
    PRE_CREATE, POST_CREATE, PRE_UPDATE, POST_UPDATE,
    PRE_DELETE, POST_DELETE, PRE_FETCH, POST_FETCH
"""

from lib.hooks import hooks, HookPoint  # noqa: F401

# Register your hooks below:
