"""
User Management Service for handling user profile operations.

Manages user profile updates, deactivation, and deletion.
"""

import logging
from typing import Optional
from datetime import datetime, timedelta

from domain.model import User, Profile
from services.authorization.domain.enums import UserState, AuthOperation
from services.authorization.domain.exceptions import (
    UserNotFoundError,
    InvalidEmailError,
    InvalidStateTransitionError
)
from services.authorization.domain.responses import UserUpdateResponse, AuthResponse
from data.generic_dao import GenericDAO
from services.email.email_service import EmailService
from services.authorization.utils.validators import EmailValidator
from services.authorization.utils.audit_logger import AuditLogger, AuditEventType

logger = logging.getLogger(__name__)


class UserManagementService:
    """
    Handles user profile and account management operations.
    
    Manages profile updates, account deactivation, and deletion with
    proper state management and audit logging.
    """
    
    def __init__(
        self,
        dao: GenericDAO,
        email_service: EmailService,
        audit_logger: AuditLogger
    ):
        """
        Initialize user management service.
        
        Args:
            dao: Data access object for database operations
            email_service: Service for sending emails
            audit_logger: Logger for audit events
        """
        self.dao = dao
        self.email_service = email_service
        self.audit_logger = audit_logger
    
    def update_profile(
        self,
        user_id: str,
        changes: Profile,
        ip_address: Optional[str] = None
    ) -> UserUpdateResponse:
        """
        Update user profile with changes.
        
        If email is changed, triggers email validation workflow.
        
        Args:
            user_id: ID of user to update
            changes: Profile object with fields to update
            ip_address: IP address of request
            
        Returns:
            UserUpdateResponse with updated profile
            
        Raises:
            UserNotFoundError: If user or profile doesn't exist
            InvalidEmailError: If new email format is invalid
        """
        # Clean user_id
        user_id = user_id.split("/")[-1]
        
        # Find existing profile
        profile = self.dao.find_by_id(entity=Profile, id=user_id)
        if not profile:
            raise UserNotFoundError()
        
        # Check if email is changing
        email_changed = False
        if changes.email and changes.email != profile.email:
            # Validate new email
            changes.email = EmailValidator.validate(changes.email)
            email_changed = True
        
        # Merge changes into profile
        profile = self._merge_profiles(profile, changes)
        
        # Update profile
        self.dao.update(entity=Profile, id=profile.id, data=profile)
        
        # If email changed, update user and require validation
        requires_validation = False
        if email_changed:
            requires_validation = self._handle_email_change(
                user_id, profile.email, profile.name, ip_address
            )
        
        # Log update
        self.audit_logger.log_event(
            AuditEventType.PROFILE_UPDATED,
            user_id=user_id,
            email=profile.email,
            ip_address=ip_address,
            success=True,
            details={"email_changed": email_changed}
        )
        
        logger.info(f"User profile updated: {user_id}")
        
        return UserUpdateResponse(
            success=True,
            operation=AuthOperation.USER_PROFILE_UPDATED,
            profile=profile,
            requires_email_validation=requires_validation,
            message="Profile updated successfully" + (
                ". Please validate your new email address on next login." if requires_validation else ""
            )
        )
    
    def deactivate_account(
        self,
        user_id: str,
        ip_address: Optional[str] = None,
        admin_action: bool = False
    ) -> AuthResponse:
        """
        Deactivate user account.
        
        Account is marked for deletion after 90 days.
        
        Args:
            user_id: ID of user to deactivate
            ip_address: IP address of request
            admin_action: Whether this is an admin-initiated action
            
        Returns:
            AuthResponse indicating success
            
        Raises:
            UserNotFoundError: If user doesn't exist
            InvalidStateTransitionError: If state transition is invalid
        """
        user = self.dao.find_by_id(entity=User, id=user_id)
        if not user:
            raise UserNotFoundError()
        
        # Validate state transition
        if not UserState.can_transition(user.state, UserState.DEACTIVATED):
            raise InvalidStateTransitionError(user.state, UserState.DEACTIVATED)
        
        # Update user state
        user.state = UserState.DEACTIVATED
        user.delete_date = datetime.now() + timedelta(days=90)
        self.dao.update(entity=User, id=user.id, data=user)
        
        # Log deactivation
        self.audit_logger.log_event(
            AuditEventType.ACCOUNT_DEACTIVATED,
            user_id=user_id,
            email=user.email,
            ip_address=ip_address,
            success=True,
            details={
                "admin_action": admin_action,
                "scheduled_deletion": user.delete_date.isoformat()
            }
        )
        
        # Send notification
        try:
            self.email_service.send_message(
                email=user.email,
                subject="Account Deactivated",
                message=f"Hi {user.name},\n\n"
                       f"Your account has been deactivated.\n\n"
                       f"Your data will be permanently deleted on {user.delete_date.strftime('%Y-%m-%d')}.\n\n"
                       f"If you want to reactivate your account, please contact support before this date."
            )
        except Exception as e:
            logger.error(f"Failed to send deactivation email: {e}")
        
        logger.info(f"User account deactivated: {user_id}")
        
        return AuthResponse(
            success=True,
            operation=AuthOperation.USER_DEACTIVATED,
            message=f"Account deactivated. Data will be deleted on {user.delete_date.strftime('%Y-%m-%d')}."
        )
    
    def delete_account(
        self,
        user_id: str,
        ip_address: Optional[str] = None,
        admin_action: bool = False
    ) -> AuthResponse:
        """
        Permanently delete user account and profile.
        
        Args:
            user_id: ID of user to delete
            ip_address: IP address of request
            admin_action: Whether this is an admin-initiated action
            
        Returns:
            AuthResponse indicating success
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        user = self.dao.find_by_id(entity=User, id=user_id)
        if not user:
            raise UserNotFoundError()
        
        email = user.email
        name = user.name
        
        # Delete user (hard delete)
        user_deleted = self.dao.delete(entity=User, id=user_id)
        
        # Delete profile (soft delete to maintain referential integrity)
        profile_deleted = self.dao.delete(
            entity=Profile,
            id=user_id,
            physical_delete=False
        )
        
        if not user_deleted:
            raise UserNotFoundError()
        
        # Log deletion
        self.audit_logger.log_event(
            AuditEventType.ACCOUNT_DELETED,
            user_id=user_id,
            email=email,
            ip_address=ip_address,
            success=True,
            details={
                "admin_action": admin_action,
                "profile_deleted": profile_deleted
            }
        )
        
        logger.info(f"User account deleted: {user_id}")
        
        # Send confirmation if not admin action
        if not admin_action:
            try:
                self.email_service.send_message(
                    email=email,
                    subject="Account Deleted",
                    message=f"Hi {name},\n\n"
                           f"Your account has been permanently deleted.\n\n"
                           f"All your data has been removed from our systems.\n\n"
                           f"Thank you for using our service."
                )
            except Exception as e:
                logger.error(f"Failed to send deletion confirmation: {e}")
        
        return AuthResponse(
            success=True,
            operation=AuthOperation.USER_DELETED,
            message="Account deleted successfully"
        )
    
    def reactivate_account(
        self,
        user_id: str,
        ip_address: Optional[str] = None
    ) -> AuthResponse:
        """
        Reactivate a deactivated account.
        
        Args:
            user_id: ID of user to reactivate
            ip_address: IP address of request
            
        Returns:
            AuthResponse indicating success
            
        Raises:
            UserNotFoundError: If user doesn't exist
            InvalidStateTransitionError: If not currently deactivated
        """
        user = self.dao.find_by_id(entity=User, id=user_id)
        if not user:
            raise UserNotFoundError()
        
        if user.state != UserState.DEACTIVATED:
            raise InvalidStateTransitionError(
                user.state,
                UserState.ACTIVE
            )
        
        # Reactivate user
        user.state = UserState.ACTIVE
        user.delete_date = None
        self.dao.update(entity=User, id=user.id, data=user)
        
        # Log reactivation
        self.audit_logger.log_event(
            AuditEventType.ACCOUNT_ACTIVATED,
            user_id=user_id,
            email=user.email,
            ip_address=ip_address,
            success=True,
            details={"reactivation": True}
        )
        
        logger.info(f"User account reactivated: {user_id}")
        
        return AuthResponse(
            success=True,
            operation=AuthOperation.ACTIVE,
            message="Account reactivated successfully"
        )
    
    def _merge_profiles(self, existing: Profile, changes: Profile) -> Profile:
        """
        Merge changes into existing profile.
        
        Args:
            existing: Current profile
            changes: Profile with fields to update
            
        Returns:
            Merged profile
        """
        existing_dict = existing.model_dump(by_alias=False)
        changes_dict = changes.model_dump(by_alias=False)
        
        # Update only non-None values
        for key, value in changes_dict.items():
            if value is not None:
                existing_dict[key] = value
        
        return Profile(**existing_dict)
    
    def _handle_email_change(
        self,
        user_id: str,
        new_email: str,
        name: str,
        ip_address: Optional[str]
    ) -> bool:
        """
        Handle email change by updating user and requiring validation.
        
        Args:
            user_id: User ID
            new_email: New email address
            name: User name
            ip_address: IP address of request
            
        Returns:
            True if validation is required
        """
        user = self.dao.find_by_id(entity=User, id=user_id)
        if not user:
            return False
        
        # Update user email
        user.email = new_email
        user.name = name
        
        # Require email validation on next login
        if user.state == UserState.ACTIVE:
            user.state = UserState.PREREGISTERED
            self.dao.update(entity=User, id=user.id, data=user)
            
            logger.info(f"Email changed for user {user_id}, validation required")
            return True
        
        return False
