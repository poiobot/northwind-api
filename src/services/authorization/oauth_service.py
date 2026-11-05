"""
OAuth Service for handling OAuth2 authentication.

Manages OAuth login flow with proper token verification and user creation.
"""

import logging
from typing import Optional, Dict, Any

from domain.model import User, Profile
from domain.common.user_credentials import UserCredentials
from services.authorization.domain.enums import UserState, LoginType, AuthOperation
from services.authorization.domain.exceptions import InvalidTokenError
from services.authorization.domain.responses import LoginResponse
from data.generic_dao import GenericDAO
from services.authorization.authorization_handler import (
    AuthorizationHandler,
    ExpiredToken,
    InvalidTokenSignature,
    TokenValidationError
)
from services.authorization.utils.audit_logger import AuditLogger, AuditEventType

logger = logging.getLogger(__name__)


class OAuthService:
    """
    Handles OAuth2 authentication flow.
    
    Manages secure verification of OAuth tokens and auto-provisioning
    of user accounts from OAuth provider data.
    """
    
    # Allowed OAuth email domains (whitelist for auto-registration)
    ALLOWED_DOMAINS = {
        # Add your allowed domains here, or set to None to allow all
        # 'company.com', 'partner.com'
    }
    
    def __init__(
        self,
        dao: GenericDAO,
        auth_handler: AuthorizationHandler,
        audit_logger: AuditLogger
    ):
        """
        Initialize OAuth service.
        
        Args:
            dao: Data access object for database operations
            auth_handler: Authorization handler for token operations
            audit_logger: Logger for audit events
        """
        self.dao = dao
        self.auth_handler = auth_handler
        self.audit_logger = audit_logger
    
    def oauth_login(
        self,
        oauth_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> LoginResponse:
        """
        Authenticate user via OAuth2 token.
        
        Validates OAuth token, creates user if necessary, and returns JWT.
        
        Args:
            oauth_token: OAuth token from provider (Google, Microsoft, etc.)
            ip_address: IP address of request
            user_agent: User agent string
            
        Returns:
            LoginResponse with profile and JWT token
            
        Raises:
            InvalidTokenError: If OAuth token is invalid or expired
        """
        # Decode and validate OAuth token
        user_details = self._validate_oauth_token(oauth_token)
        
        email = user_details.get("email")
        if not email:
            raise InvalidTokenError("OAuth token missing email claim")
        
        email = email.lower().strip()
        
        # Check domain whitelist if configured
        if self.ALLOWED_DOMAINS:
            domain = email.split('@')[1]
            if domain not in self.ALLOWED_DOMAINS:
                logger.warning(f"OAuth login attempted from unauthorized domain: {domain}")
                self.audit_logger.log_event(
                    AuditEventType.OAUTH_LOGIN_FAILURE,
                    email=email,
                    ip_address=ip_address,
                    success=False,
                    details={"reason": "Unauthorized domain"}
                )
                raise InvalidTokenError(
                    "OAuth login not allowed for this email domain"
                )
        
        # Identify or create user
        user, profile, is_new_user = self._identify_or_create_user(user_details)
        
        # Check if user is deactivated
        if user.state == UserState.DEACTIVATED:
            self.audit_logger.log_event(
                AuditEventType.OAUTH_LOGIN_FAILURE,
                user_id=user.id,
                email=email,
                ip_address=ip_address,
                success=False,
                details={"reason": "Account deactivated"}
            )
            raise InvalidTokenError("Account has been deactivated")
        
        # Generate application JWT token
        user_credentials = UserCredentials(**profile.model_dump(by_alias=False))
        jwt_token = self.auth_handler.encode_token(credentials=user_credentials)
        
        # Log successful OAuth login
        self.audit_logger.log_event(
            AuditEventType.OAUTH_LOGIN_SUCCESS,
            user_id=user.id,
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
            details={
                "is_new_user": is_new_user,
                "provider": user_details.get("provider", "unknown")
            }
        )
        
        logger.info(f"OAuth login successful: {user.id} ({email}), new_user={is_new_user}")
        
        operation = AuthOperation.USER_CREATED if is_new_user else AuthOperation.CONNECTED
        
        return LoginResponse(
            success=True,
            operation=operation,
            profile=profile,
            token=jwt_token,
            user_id=user.id,
            message="Login successful" if not is_new_user else "Account created and logged in"
        )
    
    def _validate_oauth_token(self, oauth_token: str) -> Dict[str, Any]:
        """
        Validate OAuth token and extract user details.
        
        CRITICAL: This properly verifies the token signature and expiration.
        
        Args:
            oauth_token: OAuth token from provider
            
        Returns:
            Dictionary containing user details from token
            
        Raises:
            InvalidTokenError: If token is invalid or expired
        """
        try:
            # Use proper decode_token that verifies signature
            # Assumes OAuth token is in JWT format issued by our auth handler
            # or a trusted OAuth provider's token that we can verify
            
            # For external OAuth providers (Google, Microsoft, etc.),
            # you would validate using their public keys here
            # For now, this assumes internal OAuth tokens
            
            payload = self.auth_handler.decode_token(oauth_token)
            
            # For external OAuth, you would extract claims differently
            # This is a simplified example
            user_details = {
                "email": getattr(payload, 'email', None),
                "name": getattr(payload, 'name', None),
                "picture": getattr(payload, 'avatar', None),
                "provider": "internal"  # Would be 'google', 'microsoft', etc.
            }
            
            return user_details
            
        except ExpiredToken:
            logger.warning("Expired OAuth token")
            raise InvalidTokenError("OAuth token has expired")
        except InvalidTokenSignature:
            logger.warning("Invalid OAuth token signature")
            raise InvalidTokenError("OAuth token signature is invalid")
        except TokenValidationError as e:
            logger.warning(f"OAuth token validation failed: {e}")
            raise InvalidTokenError(f"OAuth token validation failed: {str(e)}")
    
    def _identify_or_create_user(
        self,
        user_details: Dict[str, Any]
    ) -> tuple[User, Profile, bool]:
        """
        Find existing user or create new one from OAuth details.
        
        Args:
            user_details: Dictionary containing user info from OAuth token
            
        Returns:
            Tuple of (User, Profile, is_new_user)
        """
        email = user_details.get("email").lower().strip()
        
        # Try to find existing user
        existing_users = list(
            self.dao.find_by_key_value(entity=User, key="email", value=email)
        )
        
        if existing_users:
            # User exists
            user = existing_users[0]
            
            # Update login type to OAuth if it was unknown
            if user.login_type == LoginType.UNKNOWN:
                user.login_type = LoginType.OAUTH2
                self.dao.update(entity=User, id=user.id, data=user)
            
            # Get profile
            profile = self.dao.find_by_id(entity=Profile, id=user.id)
            
            # Update profile with latest OAuth data
            if profile:
                if user_details.get("name"):
                    profile.name = user_details["name"]
                if user_details.get("picture"):
                    profile.avatar = user_details["picture"]
                self.dao.update(entity=Profile, id=profile.id, data=profile)
            
            return user, profile, False
        
        else:
            # Create new user
            return self._create_oauth_user(user_details)
    
    def _create_oauth_user(
        self,
        user_details: Dict[str, Any]
    ) -> tuple[User, Profile, bool]:
        """
        Create a new user from OAuth details.
        
        Args:
            user_details: Dictionary containing user info from OAuth token
            
        Returns:
            Tuple of (User, Profile, is_new_user=True)
        """
        from bson.objectid import ObjectId
        
        user_id = str(ObjectId())
        email = user_details.get("email").lower().strip()
        name = user_details.get("name") or email.split('@')[0]
        
        # Create user
        user_data = User(
            id=user_id,
            email=email,
            name=name,
            login_type=LoginType.OAUTH2,
            state=UserState.ACTIVE,  # OAuth users are pre-validated by provider
            profile=user_id
        )
        user = self.dao.insert(entity=User, data=user_data)
        
        # Create profile
        profile_data = Profile(
            id=user_id,
            name=name,
            email=email,
            avatar=user_details.get("picture"),
            roles=["user"],  # Default role for OAuth users
            phone=""
        )
        profile = self.dao.insert(entity=Profile, data=profile_data)
        
        logger.info(f"Created new OAuth user: {user_id} ({email})")
        
        return user, profile, True
