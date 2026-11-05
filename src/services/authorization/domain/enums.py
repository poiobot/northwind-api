"""
Enums for authentication and user management.

Provides type-safe constants for user states, login types, and operation results.
"""

from enum import Enum


class UserState(str, Enum):
    """
    User account states with defined transitions.
    
    State Machine:
        PREREGISTERED -> VALIDATE_EMAIL (via registration)
        VALIDATE_EMAIL -> ACTIVE (via code validation)
        ACTIVE -> DEACTIVATED (via user/admin action)
        DEACTIVATED -> DELETED (automated cleanup)
        Any state -> DELETED (admin action)
    """
    PREREGISTERED = "PREREGISTERED"
    VALIDATE_EMAIL = "VALIDATE_EMAIL"
    ACTIVE = "ACTIVE"
    DEACTIVATED = "DEACTIVATED"
    DELETED = "DELETED"
    
    @classmethod
    def can_transition(cls, from_state: 'UserState', to_state: 'UserState') -> bool:
        """
        Check if a state transition is valid.
        
        Args:
            from_state: Current user state
            to_state: Desired user state
            
        Returns:
            True if transition is allowed, False otherwise
        """
        valid_transitions = {
            cls.PREREGISTERED: [cls.VALIDATE_EMAIL, cls.DELETED],
            cls.VALIDATE_EMAIL: [cls.ACTIVE, cls.DELETED, cls.PREREGISTERED],
            cls.ACTIVE: [cls.DEACTIVATED, cls.DELETED, cls.VALIDATE_EMAIL],
            cls.DEACTIVATED: [cls.ACTIVE, cls.DELETED],
            cls.DELETED: []  # Terminal state
        }
        
        return to_state in valid_transitions.get(from_state, [])


class LoginType(str, Enum):
    """User login/registration method."""
    MANUAL = "MANUAL"
    OAUTH2 = "OAUTH2"
    UNKNOWN = "UNKNOWN"


class AuthOperation(str, Enum):
    """Results of authentication operations."""
    # Success states
    CONNECTED = "CONNECTED"
    PREREGISTERED = "PREREGISTERED"
    REGISTERED = "REGISTERED"
    ACTIVE = "ACTIVE"
    USER_IDENTIFIED = "USER_IDENTIFIED"
    USER_CREATED = "USER_CREATED"
    USER_PROFILE_UPDATED = "USER_PROFILE_UPDATED"
    USER_DEACTIVATED = "USER_DEACTIVATED"
    USER_DELETED = "USER_DELETED"
    PASSWORD_RESET = "PASSWORD_RESET"
    EMAIL_VALIDATION_CODE_SENT = "EMAIL_VALIDATION_CODE_SENT"
    VALID_CODE = "VALID_CODE"
    
    # Error states
    INVALID_EMAIL_FORMAT = "INVALID_EMAIL_FORMAT"
    USER_ALREADY_REGISTERED = "USER_ALREADY_REGISTERED"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    VALIDATE_EMAIL = "VALIDATE_EMAIL"
    USER_DEACTIVATED_ERROR = "USER_DEACTIVATED_ERROR"
    INVALID_CODE = "INVALID_CODE"
    TOO_MANY_ATTEMPTS = "TOO_MANY_ATTEMPTS"
    REGISTER_AGAIN = "REGISTER_AGAIN"
    EXPIRED_TOKEN = "EXPIRED_TOKEN"
    INVALID_TOKEN = "INVALID_TOKEN"
    EMAIL_NOT_FOUND = "EMAIL_NOT_FOUND"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
