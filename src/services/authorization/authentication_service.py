"""
Authentication Service for handling login operations.

Manages user authentication, code validation, and account activation.
"""

import logging
from typing import Optional

from domain.model import User, Profile
from domain.common.user_credentials import UserCredentials
from services.authorization.domain.enums import UserState, AuthOperation
from services.authorization.domain.exceptions import (
    InvalidCredentialsError,
    UserNotFoundError,
    EmailNotValidatedError,
    UserDeactivatedError,
    InvalidCodeError,
    TooManyAttemptsError,
    RateLimitExceededError
)
from services.authorization.domain.responses import LoginResponse, CodeValidationResponse
from data.generic_dao import GenericDAO
from services.authorization.authorization_handler import AuthorizationHandler
from services.email.email_service import EmailService
from services.authorization.utils.validators import EmailValidator, PasswordValidator
from services.authorization.utils.audit_logger import AuditLogger, AuditEventType
from services.authorization.utils.rate_limiter import login_rate_limiter, code_validation_rate_limiter

logger = logging.getLogger(__name__)


class AuthenticationService:
    """
    Handles user authentication and validation operations.
    
    Manages login, code validation, and account activation with
    rate limiting and security controls.
    """
    
    def __init__(
        self,
        dao: GenericDAO,
        auth_handler: AuthorizationHandler,
        email_service: EmailService,
        audit_logger: AuditLogger
    ):
        """
        Initialize authentication service.
        
        Args:
            dao: Data access object for database operations
            auth_handler: Authorization handler for token generation
            email_service: Service for sending emails
            audit_logger: Logger for audit events
        """
        self.dao = dao
        self.auth_handler = auth_handler
        self.email_service = email_service
        self.audit_logger = audit_logger
    
    def login(
        self,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> LoginResponse:
        """
        Authenticate user with email and password.
        
        Args:
            email: User's email address
            password: User's password
            ip_address: IP address of login request
            user_agent: User agent string
            
        Returns:
            LoginResponse with profile and JWT token
            
        Raises:
            InvalidCredentialsError: If email or password is incorrect
            EmailNotValidatedError: If user hasn't validated email
            UserDeactivatedError: If user account is deactivated
            RateLimitExceededError: If too many login attempts
        """
        # Normalize email
        email = email.lower().strip()
        
        # Check rate limit
        if not login_rate_limiter.record_attempt(email):
            remaining_time = login_rate_limiter.get_lockout_time_remaining(email)
            self.audit_logger.log_login_failure(
                email=email,
                reason="Rate limit exceeded",
                ip_address=ip_address,
                user_agent=user_agent
            )
            raise RateLimitExceededError(
                f"Too many login attempts. Please try again in {int(remaining_time.total_seconds() / 60)} minutes."
            )
        
        # Find user
        users = list(
            self.dao.find_by_key_value(entity=User, key="email", value=email)
        )
        
        if not users:
            self.audit_logger.log_login_failure(
                email=email,
                reason="User not found",
                ip_address=ip_address,
                user_agent=user_agent
            )
            raise InvalidCredentialsError()
        
        user = users[0]
        
        # Check account state
        if user.state == UserState.DEACTIVATED:
            self.audit_logger.log_login_failure(
                email=email,
                reason="Account deactivated",
                ip_address=ip_address,
                user_agent=user_agent
            )
            raise UserDeactivatedError()
        
        # Handle preregistered users - send validation code
        if user.state == UserState.PREREGISTERED:
            self._send_validation_code_for_preregistered(user)
            return LoginResponse(
                success=False,
                operation=AuthOperation.EMAIL_VALIDATION_CODE_SENT,
                message=f"Please check {email} for validation code to complete registration."
            )
        
        # Check if email needs validation
        if user.state == UserState.VALIDATE_EMAIL:
            self.audit_logger.log_login_failure(
                email=email,
                reason="Email not validated",
                ip_address=ip_address,
                user_agent=user_agent
            )
            raise EmailNotValidatedError()
        
        # Verify password
        if not self.auth_handler.verify_password(password, user.password):
            self.audit_logger.log_login_failure(
                email=email,
                reason="Invalid password",
                ip_address=ip_address,
                user_agent=user_agent
            )
            raise InvalidCredentialsError()
        
        # Get user profile
        profile = self.dao.find_by_id(entity=Profile, id=user.id)
        if not profile:
            logger.error(f"Profile not found for user {user.id}")
            raise InvalidCredentialsError()
        
        # Generate JWT token
        user_credentials = UserCredentials(**profile.model_dump(by_alias=False))
        jwt_token = self.auth_handler.encode_token(credentials=user_credentials)
        
        # Reset rate limiter on successful login
        login_rate_limiter.reset(email)
        
        # Log successful login
        self.audit_logger.log_login_success(
            user_id=user.id,
            email=email,
            login_type=user.login_type,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        logger.info(f"User logged in: {user.id} ({email})")
        
        return LoginResponse(
            success=True,
            operation=AuthOperation.CONNECTED,
            profile=profile,
            token=jwt_token,
            user_id=user.id,
            message="Login successful"
        )
    
    def activate(
        self,
        user_id: str,
        code: str,
        ip_address: Optional[str] = None
    ) -> CodeValidationResponse:
        """
        Activate user account by validating email code.
        
        Args:
            user_id: ID of user to activate
            code: Validation code sent to user's email
            ip_address: IP address of request
            
        Returns:
            CodeValidationResponse indicating success
            
        Raises:
            UserNotFoundError: If user doesn't exist
            InvalidCodeError: If code is incorrect
            TooManyAttemptsError: If maximum attempts exceeded
            RateLimitExceededError: If rate limit exceeded
        """
        # Check rate limit
        if not code_validation_rate_limiter.record_attempt(user_id):
            raise RateLimitExceededError(
                "Too many validation attempts. Please request a new code."
            )
        
        # Find user
        user = self.dao.find_by_id(entity=User, id=user_id)
        if not user:
            logger.warning(f"User not found: {user_id}")
            raise UserNotFoundError()
        
        # Check if user has attempts remaining
        if user.attempts <= 0:
            self.audit_logger.log_account_locked(
                user_id=user.id,
                email=user.email,
                reason="Too many failed validation attempts",
                ip_address=ip_address
            )
            # Lock the account instead of deleting
            user.state = UserState.DEACTIVATED
            self.dao.update(entity=User, id=user.id, data=user)
            raise TooManyAttemptsError(
                "Account locked due to too many failed attempts. Please contact support."
            )
        
        # Validate code
        if user.code != code:
            user.attempts -= 1
            self.dao.update(entity=User, id=user.id, data=user)
            
            self.audit_logger.log_invalid_code_attempt(
                user_id=user.id,
                email=user.email,
                attempts_left=user.attempts,
                ip_address=ip_address
            )
            
            logger.info(f"Invalid code for user {user.id}, {user.attempts} attempts left")
            raise InvalidCodeError(attempts_left=user.attempts)
        
        # Activate user
        user.state = UserState.ACTIVE
        user.code = "----"  # Clear the code
        user.attempts = 3  # Reset attempts for future operations
        self.dao.update(entity=User, id=user.id, data=user)
        
        # Reset rate limiter
        code_validation_rate_limiter.reset(user_id)
        
        # Log activation
        self.audit_logger.log_event(
            AuditEventType.EMAIL_VALIDATED,
            user_id=user.id,
            email=user.email,
            ip_address=ip_address,
            success=True
        )
        
        logger.info(f"User activated: {user.id} ({user.email})")
        
        return CodeValidationResponse(
            success=True,
            operation=AuthOperation.ACTIVE,
            user_id=user.id,
            message="Email validated successfully. You can now login."
        )
    
    def send_validation_code(
        self,
        email: str,
        ip_address: Optional[str] = None
    ) -> CodeValidationResponse:
        """
        Send or resend email validation code.
        
        Args:
            email: User's email address
            ip_address: IP address of request
            
        Returns:
            CodeValidationResponse indicating code was sent
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        email = email.lower().strip()
        
        # Find user
        users = list(
            self.dao.find_by_key_value(entity=User, key="email", value=email)
        )
        
        if not users:
            raise UserNotFoundError()
        
        user = users[0]
        
        # Generate new code
        user.code = PasswordValidator.generate_validation_code(6)
        user.attempts = 3  # Reset attempts when sending new code
        self.dao.update(entity=User, id=user.id, data=user)
        
        # Send email
        try:
            self.email_service.send_message(
                email=user.email,
                subject="Your validation code",
                message=f"Hi {user.name},\n\n"
                       f"Your verification code is: {user.code}\n\n"
                       f"This code will expire in 15 minutes.\n\n"
                       f"If you didn't request this, please ignore this email."
            )
        except Exception as e:
            logger.error(f"Failed to send validation email: {e}")
            # Continue anyway - code is saved
        
        logger.info(f"Validation code sent to {email}")
        
        return CodeValidationResponse(
            success=True,
            operation=AuthOperation.EMAIL_VALIDATION_CODE_SENT,
            message=f"Validation code sent to {email}"
        )
    
    def _send_validation_code_for_preregistered(self, user: User) -> None:
        """
        Send validation code for preregistered user attempting first login.
        
        Args:
            user: Preregistered user object
        """
        # Generate code and update state
        user.code = PasswordValidator.generate_validation_code(6)
        user.state = UserState.VALIDATE_EMAIL
        user.attempts = 3
        self.dao.update(entity=User, id=user.id, data=user)
        
        # Send email
        try:
            self.email_service.send_message(
                email=user.email,
                subject="Complete your registration",
                message=f"Hi {user.name},\n\n"
                       f"You've been invited to join our platform.\n"
                       f"Your verification code is: {user.code}\n\n"
                       f"Please use this code to complete your registration.\n\n"
                       f"If you didn't expect this invitation, please contact support."
            )
        except Exception as e:
            logger.error(f"Failed to send preregistration validation email: {e}")
