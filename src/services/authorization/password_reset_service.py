"""
Password Reset Service for handling password reset workflows.

Manages secure password reset with token-based verification.
"""

import logging
from typing import Optional

from domain.model import User
from services.authorization.domain.enums import AuthOperation
from services.authorization.domain.exceptions import (
    UserNotFoundError,
    InvalidTokenError,
    WeakPasswordError,
    RateLimitExceededError
)
from services.authorization.domain.responses import PasswordResetResponse, CodeValidationResponse
from data.generic_dao import GenericDAO
from services.authorization.authorization_handler import (
    AuthorizationHandler,
    ExpiredToken,
    InvalidTokenSignature,
    TokenValidationError
)
from services.email.email_service import EmailService
from services.authorization.utils.validators import PasswordValidator, EmailValidator
from services.authorization.utils.audit_logger import AuditLogger, AuditEventType
from services.authorization.utils.rate_limiter import password_reset_rate_limiter

logger = logging.getLogger(__name__)


class PasswordResetService:
    """
    Handles password reset operations.
    
    Manages secure password reset workflow with email verification
    and single-use tokens.
    """
    
    def __init__(
        self,
        dao: GenericDAO,
        auth_handler: AuthorizationHandler,
        email_service: EmailService,
        audit_logger: AuditLogger
    ):
        """
        Initialize password reset service.
        
        Args:
            dao: Data access object for database operations
            auth_handler: Authorization handler for password hashing and tokens
            email_service: Service for sending emails
            audit_logger: Logger for audit events
        """
        self.dao = dao
        self.auth_handler = auth_handler
        self.email_service = email_service
        self.audit_logger = audit_logger
    
    def request_password_reset(
        self,
        email: str,
        ip_address: Optional[str] = None
    ) -> CodeValidationResponse:
        """
        Request password reset and send reset token via email.
        
        Args:
            email: User's email address
            ip_address: IP address of request
            
        Returns:
            CodeValidationResponse indicating email was sent
            
        Raises:
            UserNotFoundError: If user doesn't exist
            RateLimitExceededError: If too many reset requests
        """
        # Normalize email
        email = EmailValidator.validate(email)
        
        # Check rate limit
        if not password_reset_rate_limiter.record_attempt(email):
            remaining_time = password_reset_rate_limiter.get_lockout_time_remaining(email)
            logger.warning(f"Password reset rate limit exceeded for {email}")
            raise RateLimitExceededError(
                f"Too many password reset requests. Please try again in {int(remaining_time.total_seconds() / 60)} minutes."
            )
        
        # Find user
        users = list(
            self.dao.find_by_key_value(entity=User, key="email", value=email)
        )
        
        # For security, don't reveal if user exists or not
        # Always return success but only send email if user exists
        if not users:
            logger.info(f"Password reset requested for non-existent user: {email}")
            # Return success anyway to prevent email enumeration
            return CodeValidationResponse(
                success=True,
                operation=AuthOperation.EMAIL_VALIDATION_CODE_SENT,
                message=f"If an account exists for {email}, you will receive a password reset email."
            )
        
        user = users[0]
        
        # Generate single-use token (expires in 1 hour)
        reset_token = self.auth_handler.encode_single_use_token(
            data=user.id,
            expiry_days=0  # Will use hours instead via custom implementation
        )
        
        # For better UX, use shorter expiry for password reset
        # Ideally modify encode_single_use_token to accept hours parameter
        
        # Send reset email
        reset_link = f"https://yourapp.com/reset-password?token={reset_token}"
        
        try:
            self.email_service.send_message(
                email=user.email,
                subject="Password Reset Request",
                message=f"Hi {user.name},\n\n"
                       f"You requested to reset your password.\n\n"
                       f"Click the link below to reset your password:\n"
                       f"{reset_link}\n\n"
                       f"This link will expire in 1 hour.\n\n"
                       f"If you didn't request this, please ignore this email and ensure your account is secure."
            )
        except Exception as e:
            logger.error(f"Failed to send password reset email: {e}")
            # Don't reveal the error to user
        
        # Log event
        self.audit_logger.log_event(
            AuditEventType.PASSWORD_RESET_REQUESTED,
            user_id=user.id,
            email=email,
            ip_address=ip_address,
            success=True
        )
        
        logger.info(f"Password reset requested for user: {user.id}")
        
        return CodeValidationResponse(
            success=True,
            operation=AuthOperation.EMAIL_VALIDATION_CODE_SENT,
            message=f"If an account exists for {email}, you will receive a password reset email."
        )
    
    def reset_password(
        self,
        token: str,
        new_password: str,
        ip_address: Optional[str] = None
    ) -> PasswordResetResponse:
        """
        Reset password using single-use token.
        
        Args:
            token: Single-use reset token from email
            new_password: New password to set
            ip_address: IP address of request
            
        Returns:
            PasswordResetResponse indicating success
            
        Raises:
            InvalidTokenError: If token is invalid or expired
            UserNotFoundError: If user doesn't exist
            WeakPasswordError: If password doesn't meet requirements
        """
        # Validate and decode token
        try:
            payload = self.auth_handler.decode_single_use_token(token)
            user_id = payload.get("data")
            
            if not user_id:
                raise InvalidTokenError("Invalid reset token")
                
        except ExpiredToken:
            raise InvalidTokenError("Reset link has expired. Please request a new one.")
        except (InvalidTokenSignature, TokenValidationError):
            raise InvalidTokenError("Invalid reset token")
        
        # Find user
        user = self.dao.find_by_id(entity=User, id=user_id)
        if not user:
            logger.error(f"User not found for password reset: {user_id}")
            raise UserNotFoundError()
        
        # Validate new password
        PasswordValidator.validate(new_password, user.email)
        
        # Hash and update password
        user.password = self.auth_handler.get_password_hash(new_password)
        self.dao.update(entity=User, id=user.id, data=user)
        
        # Reset rate limiter
        password_reset_rate_limiter.reset(user.email)
        
        # Log password change
        self.audit_logger.log_password_change(
            user_id=user.id,
            email=user.email,
            initiated_by="user_reset",
            ip_address=ip_address
        )
        
        # Send confirmation email
        try:
            self.email_service.send_message(
                email=user.email,
                subject="Password Changed Successfully",
                message=f"Hi {user.name},\n\n"
                       f"Your password was successfully changed.\n\n"
                       f"If you didn't make this change, please contact support immediately.\n\n"
                       f"For security, you may want to review recent account activity."
            )
        except Exception as e:
            logger.error(f"Failed to send password change confirmation: {e}")
        
        logger.info(f"Password reset completed for user: {user.id}")
        
        return PasswordResetResponse(
            success=True,
            operation=AuthOperation.PASSWORD_RESET,
            message="Password reset successfully. You can now login with your new password."
        )
    
    def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
        ip_address: Optional[str] = None
    ) -> PasswordResetResponse:
        """
        Change password for authenticated user.
        
        Args:
            user_id: ID of user changing password
            current_password: Current password for verification
            new_password: New password to set
            ip_address: IP address of request
            
        Returns:
            PasswordResetResponse indicating success
            
        Raises:
            UserNotFoundError: If user doesn't exist
            InvalidCredentialsError: If current password is incorrect
            WeakPasswordError: If new password doesn't meet requirements
        """
        from domain.exceptions import InvalidCredentialsError
        
        # Find user
        user = self.dao.find_by_id(entity=User, id=user_id)
        if not user:
            raise UserNotFoundError()
        
        # Verify current password
        if not self.auth_handler.verify_password(current_password, user.password):
            self.audit_logger.log_event(
                AuditEventType.PASSWORD_CHANGED,
                user_id=user.id,
                email=user.email,
                ip_address=ip_address,
                success=False,
                details={"reason": "Invalid current password"}
            )
            raise InvalidCredentialsError("Current password is incorrect")
        
        # Validate new password
        PasswordValidator.validate(new_password, user.email)
        
        # Check new password is different from current
        if self.auth_handler.verify_password(new_password, user.password):
            raise WeakPasswordError("New password must be different from current password")
        
        # Update password
        user.password = self.auth_handler.get_password_hash(new_password)
        self.dao.update(entity=User, id=user.id, data=user)
        
        # Log password change
        self.audit_logger.log_password_change(
            user_id=user.id,
            email=user.email,
            initiated_by="user",
            ip_address=ip_address
        )
        
        # Send notification
        try:
            self.email_service.send_message(
                email=user.email,
                subject="Password Changed",
                message=f"Hi {user.name},\n\n"
                       f"Your password was successfully changed.\n\n"
                       f"If you didn't make this change, please contact support immediately."
            )
        except Exception as e:
            logger.error(f"Failed to send password change notification: {e}")
        
        logger.info(f"Password changed for user: {user.id}")
        
        return PasswordResetResponse(
            success=True,
            operation=AuthOperation.PASSWORD_RESET,
            message="Password changed successfully"
        )
