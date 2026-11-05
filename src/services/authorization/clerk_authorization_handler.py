"""
Clerk Authorization Handler for FastAPI.

Verifies Clerk-issued session JWTs using the Clerk Python SDK's
authenticate_request method and maps them to the existing
UserCredentials model used across the Keeper API.
"""

import logging
from typing import List, Optional
import httpx

from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions

from fastapi import Request, Security, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from domain.common.user_credentials import UserCredentials
from domain.model import Profile
from data.generic_dao import GenericDAO
from api import settings

logger = logging.getLogger(__name__)


class ClerkAuthorizationHandler:
    """
    Verifies Clerk session tokens and resolves them to local UserCredentials.

    Flow:
    1. Extract Bearer token from Authorization header
    2. Build an httpx.Request so the Clerk SDK can verify it
    3. On success, use the Clerk user's external_id (telegram_user_id) to
       look up the local Profile
    4. Return UserCredentials for downstream use
    """

    def __init__(self):
        self.security = HTTPBearer()
        self.clerk = Clerk(bearer_auth=settings.CLERK_SECRET_KEY)
        self.dao = GenericDAO()

    def _verify_clerk_token(self, token: str) -> dict:
        """
        Verify a Clerk session token and return the decoded payload.

        :param token: Bearer token from Authorization header
        :return: Decoded JWT payload dict
        :raises HTTPException: If token is invalid or expired
        """
        fake_request = httpx.Request(
            method="GET",
            url="https://localhost",
            headers={"Authorization": f"Bearer {token}"}
        )

        request_state = self.clerk.authenticate_request(
            fake_request,
            AuthenticateRequestOptions()
        )

        if not request_state.is_signed_in:
            reason = getattr(request_state, 'reason', 'Unknown')
            logger.warning(f"Clerk token verification failed: {reason}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid or expired session token: {reason}",
                headers={"WWW-Authenticate": "Bearer"}
            )

        return request_state.payload

    def _resolve_credentials(self, payload: dict) -> UserCredentials:
        """
        Map a verified Clerk JWT payload to a local UserCredentials.

        Looks up the Profile by Clerk's 'sub' (user ID) stored as
        external reference, or falls back to creating minimal credentials
        from the token claims.

        :param payload: Decoded Clerk JWT payload
        :return: UserCredentials
        """
        clerk_user_id = payload.get("sub")

        # Try to find profile by clerk_user_id stored in profile
        profiles = list(self.dao.fetch(
            entity=Profile,
            query=[("clerk_user_id", "==", clerk_user_id)]
        ))

        if profiles:
            profile = profiles[0]
            return UserCredentials(
                id=profile.id,
                name=profile.name,
                email=profile.email,
                roles=profile.roles
            )

        # No local profile found — return credentials from token
        logger.warning(f"No local profile for Clerk user {clerk_user_id}")
        return UserCredentials(
            id=clerk_user_id,
            name=payload.get("name"),
            email=payload.get("email"),
            roles=["user"]
        )

    def verify_token_dependency(
            self,
            auth: HTTPAuthorizationCredentials = Security(HTTPBearer())
    ) -> UserCredentials:
        """
        FastAPI dependency that verifies a Clerk session token.

        Usage:
            @router.get("/protected")
            async def endpoint(
                credentials: UserCredentials = Depends(clerk_handler.verify_token_dependency)
            ):
                ...
        """
        payload = self._verify_clerk_token(auth.credentials)
        return self._resolve_credentials(payload)

    def require_roles(self, allowed_roles: List[str]):
        """
        Dependency factory for role-based access control with Clerk tokens.

        Usage:
            @router.get("/admin")
            async def admin_endpoint(
                creds: UserCredentials = Depends(clerk_handler.require_roles(["admin"]))
            ):
                ...
        """
        def role_checker(
                credentials: UserCredentials = Depends(self.verify_token_dependency)
        ) -> UserCredentials:
            user_roles = credentials.roles or []
            if not any(role in user_roles for role in allowed_roles):
                logger.warning(
                    f"Access denied for {credentials.id}. "
                    f"Required: {allowed_roles}, has: {user_roles}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required one of: {', '.join(allowed_roles)}"
                )
            return credentials

        return role_checker
