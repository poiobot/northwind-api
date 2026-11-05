"""
Registration Service for handling user registration workflows.

Handles both manual registration and admin-initiated preregistration.
"""

import logging
from typing import List, Optional
from bson.objectid import ObjectId

from domain.model import User, Profile
from services.authorization.domain.enums import UserState, LoginType, AuthOperation
from services.authorization.domain.exceptions import (
    InvalidEmailError,
    UserAlreadyExistsError,
    WeakPasswordError
)
from services.authorization.domain.responses import RegistrationResponse
from data.generic_dao import GenericDAO
from services.authorization.authorization_handler import AuthorizationHandler
from services.email.email_service import EmailService
from services.authorization.utils.validators import EmailValidator, PasswordValidator
from services.authorization.utils.audit_logger import AuditLogger, AuditEventType

logger = logging.getLogger(__name__)


class RegistrationService:
    """
    Handles user registration operations.
    
    Supports both admin-initiated preregistration (with invitations)
    and self-service registration.
    """
    
    def __init__(
        self,
        dao: GenericDAO,
        auth_handler: AuthorizationHandler,
        email_service: EmailService,
        audit_logger: AuditLogger
    ):
        """
        Initialize registration service.
        
        Args:
            dao: Data access object for database operations
            auth_handler: Authorization handler for password hashing
            email_service: Service for sending emails
            audit_logger: Logger for audit events
        """
        self.dao = dao
        self.auth_handler = auth_handler
        self.email_service = email_service
        self.audit_logger = audit_logger
    
    def preregister(
        self,
        user: User,
        roles: Optional[List[str]] = None,
        ip_address: Optional[str] = None,
        **profile_payload
    ) -> RegistrationResponse:
        """
        Preregister a user (admin-initiated invitation).
        
        Creates a user in PREREGISTERED state with assigned roles.
        User must complete email validation on first login.
        
        Args:
            user: User object with basic information
            roles: List of roles to assign to the user
            ip_address: IP address of the admin creating the user
            **profile_payload: Additional profile fields
            
        Returns:
            RegistrationResponse with user_id
            
        Raises:
            InvalidEmailError: If email format is invalid
        """
        # Validate and normalize email
        user.email = EmailValidator.validate(user.email)
        
        # Check if user already exists
        existing_users = list(
            self.dao.find_by_key_value(entity=User, key="email", value=user.email)
        )
        
        if existing_users:
            existing_user = existing_users[0]
            
            # Only allow updating if user is PREREGISTERED or VALIDATE_EMAIL
            if existing_user.state not in [UserState.PREREGISTERED, UserState.VALIDATE_EMAIL]:
                raise UserAlreadyExistsError(
                    f"User already exists with state: {existing_user.state}"
                )
            
            # Update existing preregistered user
            user_id = existing_user.id
            existing_user.name = user.name
            existing_user.state = UserState.PREREGISTERED
            existing_user.login_type = LoginType.UNKNOWN
            self.dao.update(entity=User, id=existing_user.id, data=existing_user)
        else:
            # Create new user
            user_id = str(ObjectId())
            user.id = user_id
            user.profile = user_id
            user.state = UserState.PREREGISTERED
            user.login_type = LoginType.UNKNOWN
            self.dao.insert(entity=User, data=user)
        
        # Create or update profile
        profile = self.dao.find_by_id(entity=Profile, id=user_id)
        
        if profile:
            # Update existing profile
            profile.name = user.name
            profile.email = user.email
            
            # Union roles (add new roles to existing ones)
            existing_roles = set(profile.roles or [])
            new_roles = set(roles or [])
            profile.roles = list(existing_roles.union(new_roles))
            
            # Update additional fields
            for key, value in profile_payload.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)
            
            self.dao.update(entity=Profile, id=profile.id, data=profile)
        else:
            # Create new profile
            profile = Profile(
                id=user_id,
                name=user.name,
                email=user.email,
                roles=roles or ["user"],
                **profile_payload
            )
            self.dao.insert(entity=Profile, data=profile)
        
        # Log audit event
        self.audit_logger.log_event(
            AuditEventType.USER_PREREGISTERED,
            user_id=user_id,
            email=user.email,
            ip_address=ip_address,
            success=True,
            details={"roles": roles}
        )
        
        logger.info(f"User preregistered: {user_id} ({user.email})")
        
        return RegistrationResponse(
            success=True,
            operation=AuthOperation.PREREGISTERED,
            user_id=user_id,
            requires_validation=True,
            message="User preregistered successfully. Email validation required on first login."
        )
    
    def register(
        self,
        user: User,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> RegistrationResponse:
        """
        Register a new user (self-service registration).
        
        Creates user in VALIDATE_EMAIL state and sends validation code.
        
        Args:
            user: User object with name, email, and password
            ip_address: IP address of registration request
            user_agent: User agent string
            
        Returns:
            RegistrationResponse with user_id
            
        Raises:
            InvalidEmailError: If email format is invalid
            WeakPasswordError: If password doesn't meet requirements
            UserAlreadyExistsError: If user is already registered and active
        """
        # Validate email
        user.email = EmailValidator.validate(user.email)
        
        # Validate password
        PasswordValidator.validate(user.password, user.email)
        
        # Check if user already exists
        existing_users = list(
            self.dao.find_by_key_value(entity=User, key="email", value=user.email)
        )
        
        if existing_users:
            existing_user = existing_users[0]
            
            # Reject if already active or validating
            if existing_user.state in [UserState.VALIDATE_EMAIL, UserState.ACTIVE]:
                raise UserAlreadyExistsError(
                    "User already registered. Please login or reset your password."
                )
            
            # Allow re-registration for preregistered users
            user_id = existing_user.id
        else:
            user_id = str(ObjectId())
        
        # Prepare user object
        user.id = user_id
        user.state = UserState.VALIDATE_EMAIL
        user.code = PasswordValidator.generate_validation_code(6)
        user.login_type = LoginType.MANUAL
        user.password = self.auth_handler.get_password_hash(user.password)
        user.profile = user_id
        user.attempts = 3  # Allow 3 validation attempts
        
        # Upsert user
        self.dao.upsert(entity=User, data=user)
        
        # Create profile if it doesn't exist
        profile = self.dao.find_by_id(entity=Profile, id=user_id)
        if not profile:
            profile = Profile(
                id=user_id,
                name=user.name,
                email=user.email,
                roles=["user"]
            )
            self.dao.insert(entity=Profile, data=profile)
        
        # Send validation email
        self._send_validation_email(user)
        
        # Log audit event
        self.audit_logger.log_event(
            AuditEventType.USER_REGISTERED,
            user_id=user_id,
            email=user.email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True
        )
        
        logger.info(f"User registered: {user_id} ({user.email})")
        
        return RegistrationResponse(
            success=True,
            operation=AuthOperation.REGISTERED,
            user_id=user_id,
            requires_validation=True,
            message=f"Registration successful. Please check {user.email} for validation code."
        )
    
    def _send_validation_email(self, user: User) -> None:
        """
        Send email validation code to user.
        
        Args:
            user: User object with email and code
        """
        try:
            self.email_service.send_message(
                email=user.email,
                subject="Verify your email address",
                message=f"Hi {user.name},\n\n"
                       f"Your verification code is: {user.code}\n\n"
                       f"This code will expire in 15 minutes.\n\n"
                       f"If you didn't request this, please ignore this email."
            )
            logger.debug(f"Validation email sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send validation email to {user.email}: {e}")
            # Don't fail registration if email fails - user can request new code
