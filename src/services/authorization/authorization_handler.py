"""
Authorization Handler for FastAPI with JWT token management.

This module provides secure JWT token encoding/decoding, password hashing,
and role-based access control for FastAPI applications.
"""

import logging
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Tuple, Union, Dict, Any, List, Optional
from authlib.jose import jwt
from authlib.jose.errors import ExpiredTokenError, BadSignatureError, InvalidClaimError
from fastapi import Security, status, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import bcrypt
import json

from domain.common.user_credentials import UserCredentials
from services.authorization.token_blacklist import get_token_blacklist

from api import settings

# Configure logging
logger = logging.getLogger(__name__)

# Constants
ENCODING_KEY = settings.ENCODING_KEY
DEFAULT_TOKEN_EXPIRY_MINUTES = int(getattr(settings, 'DEFAULT_TOKEN_EXPIRY_MINUTES', 60))
ADMIN_TOKEN_EXPIRY_MINUTES = int(getattr(settings, 'ADMIN_TIMEOUT', 480))
SINGLE_USE_TOKEN_EXPIRY_DAYS = 183


class TokenValidationError(Exception):
    """Base exception for token validation errors."""
    pass


class ExpiredToken(TokenValidationError):
    """Token has expired."""
    pass


class InvalidTokenSignature(TokenValidationError):
    """Token signature is invalid."""
    pass


class InvalidTokenClaim(TokenValidationError):
    """Token claims are invalid."""
    pass


class AuthorizationHandler:
    """
    Handles JWT token creation, validation, password hashing, and role-based access control.

    This class provides methods for:
    - Password hashing and verification using bcrypt
    - JWT token encoding and decoding
    - Role-based access control for FastAPI endpoints
    - Single-use token generation for special purposes
    """

    def __init__(self, secret_key: Optional[str] = None):
        """
        Initialize the authorization handler.

        Args:
            secret_key: Optional secret key for JWT encoding.
                       Defaults to settings.ENCODING_KEY if not provided.
        """
        self.security = HTTPBearer()
        # self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.secret = secret_key or ENCODING_KEY
        self.rounds = 12  # or higher for security

        if not self.secret or len(self.secret) < 32:
            logger.warning("Secret key is too short. Use at least 32 characters for security.")

    @staticmethod
    def get_token_identifier(token: str) -> str:
        """
        Generate a unique identifier for a token.

        Uses SHA256 hash of the token for blacklist identification.

        Args:
            token: JWT token string

        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(token.encode()).hexdigest()

    def get_password_hash(self, password: str) -> str:
        """
        Hash a password using bcrypt.

        Args:
            password: Plain text password to hash

        Returns:
            Hashed password string
        """
        # return self.pwd_context.hash(password)
        pwd_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt(rounds=self.rounds)
        return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a plain password against a hashed password.

        Args:
            plain_password: Plain text password to verify
            hashed_password: Hashed password to compare against

        Returns:
            True if password matches, False otherwise
        """
        # return self.pwd_context.verify(plain_password, hashed_password)
        pwd_bytes = plain_password.encode('utf-8')
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(pwd_bytes, hash_bytes)

    def encode_token(self, credentials: UserCredentials, custom_expiry_minutes: Optional[int] = None) -> str:
        """
        Encode user credentials into a JWT token.

        Args:
            credentials: User credentials to encode
            custom_expiry_minutes: Optional custom expiration time in minutes.
                                  If not provided, uses role-based defaults.

        Returns:
            JWT token as a string
        """
        now = datetime.now(timezone.utc)

        # Determine token expiry based on role or custom value
        if custom_expiry_minutes is not None:
            expiry_minutes = custom_expiry_minutes
        elif "super" in credentials.roles or "admin" in credentials.roles:
            expiry_minutes = ADMIN_TOKEN_EXPIRY_MINUTES
        else:
            expiry_minutes = DEFAULT_TOKEN_EXPIRY_MINUTES

        payload = {
            "sub": json.dumps(credentials.model_dump(mode="json", by_alias=False)),
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=expiry_minutes)
        }

        header = {"alg": "HS256"}
        token = jwt.encode(header, payload, self.secret)

        logger.info(f"Token encoded for user: {credentials.email}, expires in {expiry_minutes} minutes")
        return token.decode("utf-8")

    def decode_token(self, token: str, check_blacklist: bool = True) -> UserCredentials:
        """
        Decode and validate a JWT token.

        Args:
            token: JWT token string to decode
            check_blacklist: Whether to check if token is blacklisted (default: True)

        Returns:
            UserCredentials object from the token

        Raises:
            ExpiredToken: If the token has expired
            InvalidTokenSignature: If the token signature is invalid
            InvalidTokenClaim: If the token claims are invalid
            TokenValidationError: For any other validation errors (including blacklisted)
        """
        # Check blacklist first if enabled
        if check_blacklist:
            token_id = self.get_token_identifier(token)
            if get_token_blacklist().is_blacklisted(token_id):
                logger.warning(f"Attempted use of blacklisted token: {token_id[:10]}...")
                raise TokenValidationError("Token has been revoked")

        try:
            payload = jwt.decode(token, self.secret)
            payload.validate()
            credentials_dict = json.loads(payload["sub"])
            credentials = UserCredentials(**credentials_dict)

            logger.debug(f"Token decoded successfully for user: {credentials.email}")
            return credentials

        except ExpiredTokenError as e:
            logger.warning(f"Token expired: {e}")
            raise ExpiredToken("Token has expired") from e

        except BadSignatureError as e:
            logger.warning(f"Invalid token signature: {e}")
            raise InvalidTokenSignature("Invalid token signature") from e

        except InvalidClaimError as e:
            logger.warning(f"Invalid token claims: {e}")
            raise InvalidTokenClaim("Invalid token claims") from e

        except Exception as e:
            logger.error(f"Unknown token validation error: {type(e).__name__}: {e}")
            raise TokenValidationError(f"Could not validate token: {str(e)}") from e

    def decode_token_for_fastapi(self, token: str) -> UserCredentials:
        """
        Decode token and raise HTTPException if invalid or expired.
        Used internally for FastAPI dependencies.

        Args:
            token: JWT token string to decode

        Returns:
            UserCredentials object from the token

        Raises:
            HTTPException: With appropriate status code and detail message
        """
        try:
            return self.decode_token(token, check_blacklist=True)

        except ExpiredToken:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"}
            )

        except InvalidTokenSignature:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token signature",
                headers={"WWW-Authenticate": "Bearer"}
            )

        except InvalidTokenClaim:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims",
                headers={"WWW-Authenticate": "Bearer"}
            )

        except TokenValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"}
            )

    def revoke_token(self, token: str) -> bool:
        """
        Revoke a token by adding it to the blacklist.

        Used for logout functionality. The token will be blacklisted until
        its natural expiration time.

        Args:
            token: JWT token to revoke

        Returns:
            True if token was successfully revoked, False if token is invalid
        """
        try:
            # Decode token to get expiration time (without checking blacklist)
            payload = jwt.decode(token, self.secret)
            payload.validate()

            # Get token identifier
            token_id = self.get_token_identifier(token)

            # Get expiration time
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
            else:
                # If no expiration, blacklist for 24 hours
                expires_at = datetime.now(timezone.utc) + timedelta(days=1)

            # Add to blacklist
            from utils.token_blacklist import get_token_blacklist
            get_token_blacklist().blacklist_token(token_id, expires_at)

            logger.info(f"Token revoked successfully: {token_id[:10]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to revoke token: {e}")
            return False

    def verify_token_dependency(self, auth: HTTPAuthorizationCredentials = Security(HTTPBearer())) -> UserCredentials:
        """
        FastAPI dependency to verify JWT token and return UserCredentials.

        Usage:
            @router.get("/protected")
            async def protected_endpoint(
                user: UserCredentials = Depends(auth_handler.verify_token_dependency)
            ):
                return {"user": user.email}

        Args:
            auth: HTTP authorization credentials from request header

        Returns:
            UserCredentials object from the validated token

        Raises:
            HTTPException: If token is invalid, expired, or missing
        """
        return self.decode_token_for_fastapi(auth.credentials)

    def require_roles(self, allowed_roles: List[str]):
        """
        Dependency factory for role-based access control.

        Usage:
            @router.post("/admin/endpoint")
            async def admin_endpoint(
                user: UserCredentials = Depends(auth_handler.require_roles(["admin", "super"]))
            ):
                # Only users with "admin" or "super" role can access
                return {"message": "Admin access granted"}

        Args:
            allowed_roles: List of roles that are allowed to access the endpoint

        Returns:
            A dependency function that validates roles and returns UserCredentials

        Raises:
            HTTPException: With 403 status if user lacks required roles
        """
        def role_checker(
                credentials: UserCredentials = Depends(self.verify_token_dependency)
        ) -> UserCredentials:
            user_roles = credentials.roles or []

            # Check if user has any of the allowed roles
            if not any(role in user_roles for role in allowed_roles):
                logger.warning(
                    f"Access denied for user {credentials.email}. "
                    f"Required roles: {allowed_roles}, User roles: {user_roles}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required one of: {', '.join(allowed_roles)}"
                )

            logger.debug(f"Role check passed for user {credentials.email}")
            return credentials

        return role_checker

    def encode_single_use_token(self, data: str, expiry_days: int = SINGLE_USE_TOKEN_EXPIRY_DAYS) -> str:
        """
        Encode a single-use token with custom data.

        Useful for password reset links, email verification, etc.

        Args:
            data: String data to encode in the token
            expiry_days: Number of days until token expires (default: 183)

        Returns:
            JWT token as a string
        """
        now = datetime.now(timezone.utc)
        payload = {
            "data": data,
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(days=expiry_days),
        }
        header = {"alg": "HS256"}
        token = jwt.encode(header, payload, self.secret)

        logger.info(f"Single-use token created, expires in {expiry_days} days")
        return token.decode("utf-8")

    def decode_single_use_token(self, token: str) -> Dict[str, Any]:
        """
        Decode and validate a single-use token.

        Args:
            token: JWT token string to decode

        Returns:
            Dictionary containing the token payload

        Raises:
            ExpiredToken: If the token has expired
            InvalidTokenSignature: If the token signature is invalid
            InvalidTokenClaim: If the token claims are invalid
            TokenValidationError: For any other validation errors
        """
        try:
            payload = jwt.decode(token, self.secret)
            payload.validate()
            logger.debug("Single-use token decoded successfully")
            return dict(payload)

        except ExpiredTokenError as e:
            logger.warning(f"Single-use token expired: {e}")
            raise ExpiredToken("Token has expired") from e

        except BadSignatureError as e:
            logger.warning(f"Invalid single-use token signature: {e}")
            raise InvalidTokenSignature("Invalid token signature") from e

        except InvalidClaimError as e:
            logger.warning(f"Invalid single-use token claims: {e}")
            raise InvalidTokenClaim("Invalid token claims") from e

        except Exception as e:
            logger.error(f"Unknown single-use token validation error: {type(e).__name__}: {e}")
            raise TokenValidationError(f"Could not validate token: {str(e)}") from e


# Singleton instance for application use
_auth_handler_instance: Optional[AuthorizationHandler] = None


def get_auth_handler() -> AuthorizationHandler:
    """
    Get or create the singleton AuthorizationHandler instance.

    Returns:
        The global AuthorizationHandler instance
    """
    global _auth_handler_instance
    if _auth_handler_instance is None:
        _auth_handler_instance = AuthorizationHandler()
    return _auth_handler_instance


def require_authentication() -> UserCredentials:
    """
    FastAPI dependency for basic authentication (any valid token).

    Usage:
        @router.get("/protected")
        async def protected_endpoint(
            user: UserCredentials = Depends(require_authentication)
        ):
            return {"user": user.email}

    Returns:
        UserCredentials from the validated token
    """
    auth_handler = get_auth_handler()
    return Depends(auth_handler.verify_token_dependency)


def require_roles(allowed_roles: List[str]):
    """
    FastAPI dependency factory for role-based access control.

    This is a convenience function that uses the singleton auth handler.

    Usage:
        @router.post("/admin/users")
        async def create_user(
            user_data: UserCreate,
            current_user: UserCredentials = Depends(require_roles(["admin", "super"]))
        ):
            # Only admins and super users can create users
            return {"created_by": current_user.email}

    Args:
        allowed_roles: List of roles that are allowed to access the endpoint

    Returns:
        A dependency function that validates roles and returns UserCredentials
    """
    auth_handler = get_auth_handler()
    return auth_handler.require_roles(allowed_roles)


if __name__ == '__main__':
    # Configure logging for testing
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    from domain.common.user_credentials import UserCredentials
    from api import settings

    print("=" * 60)
    print("Authorization Handler Test Suite")
    print("=" * 60)

    # Check encoding key
    print(f"\n1. Encoding Key Configuration:")
    print(f"   Length: {len(settings.ENCODING_KEY)} characters")
    print(f"   Preview: {settings.ENCODING_KEY[:10]}...")

    if len(settings.ENCODING_KEY) < 32:
        print("   ⚠️  WARNING: Key is too short for production use!")
    else:
        print("   ✓ Key length is adequate")

    # Initialize handler
    auth = AuthorizationHandler()

    # Test 1: Password Hashing
    print(f"\n2. Password Hashing Test:")
    test_password = "SecureP@ssw0rd123"
    hashed = auth.get_password_hash(test_password)
    print(f"   Original: {test_password}")
    print(f"   Hashed: {hashed[:50]}...")
    print(f"   Verification: {auth.verify_password(test_password, hashed)}")
    print(f"   Wrong password: {auth.verify_password('wrong', hashed)}")

    # Test 2: Regular User Token
    print(f"\n3. Regular User Token Test:")
    user_creds = UserCredentials(
        id="user123",
        name="Rusty",
        email="user@example.com",
        roles=["user"]
    )
    user_token = auth.encode_token(user_creds)
    print(f"   Generated token: {user_token[:50]}...")

    try:
        decoded_user = auth.decode_token(user_token)
        print(f"   ✓ Decoded successfully")
        print(f"   User ID: {decoded_user.id}")
        print(f"   Email: {decoded_user.email}")
        print(f"   Roles: {decoded_user.roles}")
    except Exception as e:
        print(f"   ✗ Decode failed: {e}")

    # Test 3: Admin User Token
    print(f"\n4. Admin User Token Test:")
    admin_creds = UserCredentials(
        id="admin456",
        name="Rusty",
        email="admin@example.com",
        roles=["admin", "user"]
    )
    admin_token = auth.encode_token(admin_creds)
    print(f"   Generated token: {admin_token[:50]}...")

    try:
        decoded_admin = auth.decode_token(admin_token)
        print(f"   ✓ Decoded successfully")
        print(f"   User ID: {decoded_admin.id}")
        print(f"   Email: {decoded_admin.email}")
        print(f"   Roles: {decoded_admin.roles}")
    except Exception as e:
        print(f"   ✗ Decode failed: {e}")

    # Test 4: Invalid Token
    print(f"\n5. Invalid Token Test:")
    invalid_token = "invalid.token.here"
    try:
        auth.decode_token(invalid_token)
        print(f"   ✗ Should have raised exception")
    except TokenValidationError as e:
        print(f"   ✓ Correctly rejected: {e}")

    # Test 5: Single-Use Token
    print(f"\n6. Single-Use Token Test:")
    single_use_data = "reset-password:user123:token-id-xyz"
    single_use_token = auth.encode_single_use_token(single_use_data, expiry_days=1)
    print(f"   Generated token: {single_use_token[:50]}...")

    try:
        decoded_payload = auth.decode_single_use_token(single_use_token)
        print(f"   ✓ Decoded successfully")
        print(f"   Data: {decoded_payload.get('data')}")
        print(f"   Issued at: {datetime.fromtimestamp(decoded_payload['iat'])}")
        print(f"   Expires at: {datetime.fromtimestamp(decoded_payload['exp'])}")
    except Exception as e:
        print(f"   ✗ Decode failed: {e}")

    # Test 6: Custom Expiry
    print(f"\n7. Custom Expiry Token Test:")
    custom_token = auth.encode_token(user_creds, custom_expiry_minutes=15)
    print(f"   Generated 15-minute token: {custom_token[:50]}...")

    try:
        decoded_custom = auth.decode_token(custom_token)
        print(f"   ✓ Decoded successfully")
        print(f"   Email: {decoded_custom.email}")
    except Exception as e:
        print(f"   ✗ Decode failed: {e}")

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)
