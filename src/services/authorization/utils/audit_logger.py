"""
Audit logging for authentication and user management events.

Provides structured logging of security-relevant events with context.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class AuditEventType(str, Enum):
    """Types of audit events."""
    # Authentication events
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    LOGOUT = "LOGOUT"
    
    # Registration events
    USER_REGISTERED = "USER_REGISTERED"
    USER_PREREGISTERED = "USER_PREREGISTERED"
    EMAIL_VALIDATED = "EMAIL_VALIDATED"
    
    # Password events
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    PASSWORD_RESET_REQUESTED = "PASSWORD_RESET_REQUESTED"
    PASSWORD_RESET_COMPLETED = "PASSWORD_RESET_COMPLETED"
    
    # Account events
    ACCOUNT_ACTIVATED = "ACCOUNT_ACTIVATED"
    ACCOUNT_DEACTIVATED = "ACCOUNT_DEACTIVATED"
    ACCOUNT_DELETED = "ACCOUNT_DELETED"
    PROFILE_UPDATED = "PROFILE_UPDATED"
    
    # Security events
    INVALID_CODE_ATTEMPT = "INVALID_CODE_ATTEMPT"
    TOO_MANY_ATTEMPTS = "TOO_MANY_ATTEMPTS"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    SUSPICIOUS_ACTIVITY = "SUSPICIOUS_ACTIVITY"
    
    # OAuth events
    OAUTH_LOGIN_SUCCESS = "OAUTH_LOGIN_SUCCESS"
    OAUTH_LOGIN_FAILURE = "OAUTH_LOGIN_FAILURE"


class AuditLogger:
    """
    Structured audit logging for security events.
    
    Logs events with context including user ID, IP address, and timestamp.
    """
    
    def __init__(self, logger_name: str = "audit"):
        """
        Initialize audit logger.
        
        Args:
            logger_name: Name for the logger instance
        """
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)
        
        # Ensure we have a handler
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def log_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an audit event with context.
        
        Args:
            event_type: Type of event being logged
            user_id: ID of user involved in event
            email: Email of user (for events before user creation)
            ip_address: IP address of request
            user_agent: User agent string
            success: Whether the operation succeeded
            details: Additional event-specific details
        """
        event_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type.value,
            "success": success,
        }
        
        if user_id:
            event_data["user_id"] = user_id
        if email:
            event_data["email"] = email
        if ip_address:
            event_data["ip_address"] = ip_address
        if user_agent:
            event_data["user_agent"] = user_agent
        if details:
            event_data["details"] = details
        
        # Log at appropriate level based on event type
        if not success or event_type in [
            AuditEventType.LOGIN_FAILURE,
            AuditEventType.INVALID_CODE_ATTEMPT,
            AuditEventType.TOO_MANY_ATTEMPTS,
            AuditEventType.ACCOUNT_LOCKED,
            AuditEventType.SUSPICIOUS_ACTIVITY
        ]:
            self.logger.warning(f"AUDIT: {event_data}")
        else:
            self.logger.info(f"AUDIT: {event_data}")
    
    def log_login_success(
        self,
        user_id: str,
        email: str,
        login_type: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """Log successful login."""
        self.log_event(
            AuditEventType.LOGIN_SUCCESS,
            user_id=user_id,
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
            details={"login_type": login_type}
        )
    
    def log_login_failure(
        self,
        email: str,
        reason: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """Log failed login attempt."""
        self.log_event(
            AuditEventType.LOGIN_FAILURE,
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            details={"reason": reason}
        )
    
    def log_password_change(
        self,
        user_id: str,
        email: str,
        initiated_by: str = "user",
        ip_address: Optional[str] = None
    ) -> None:
        """Log password change event."""
        self.log_event(
            AuditEventType.PASSWORD_CHANGED,
            user_id=user_id,
            email=email,
            ip_address=ip_address,
            success=True,
            details={"initiated_by": initiated_by}
        )
    
    def log_invalid_code_attempt(
        self,
        user_id: str,
        email: str,
        attempts_left: int,
        ip_address: Optional[str] = None
    ) -> None:
        """Log invalid validation code attempt."""
        self.log_event(
            AuditEventType.INVALID_CODE_ATTEMPT,
            user_id=user_id,
            email=email,
            ip_address=ip_address,
            success=False,
            details={"attempts_left": attempts_left}
        )
    
    def log_account_locked(
        self,
        user_id: str,
        email: str,
        reason: str,
        ip_address: Optional[str] = None
    ) -> None:
        """Log account lockout event."""
        self.log_event(
            AuditEventType.ACCOUNT_LOCKED,
            user_id=user_id,
            email=email,
            ip_address=ip_address,
            success=False,
            details={"reason": reason}
        )


# Global audit logger instance
audit_logger = AuditLogger()
