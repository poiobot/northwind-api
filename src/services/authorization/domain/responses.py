"""
Response objects for authentication operations.

Provides consistent, type-safe response structures for authentication services.
"""

from typing import Optional
from pydantic import BaseModel
from domain.common.profile import Profile
from services.authorization.domain.enums import AuthOperation


class AuthResponse(BaseModel):
    """Base authentication response."""
    success: bool
    operation: AuthOperation
    message: Optional[str] = None
    
    class Config:
        use_enum_values = True


class LoginResponse(AuthResponse):
    """Response from login operation."""
    profile: Optional[Profile] = None
    token: Optional[str] = None
    user_id: Optional[str] = None


class RegistrationResponse(AuthResponse):
    """Response from registration operation."""
    user_id: Optional[str] = None
    requires_validation: bool = False


class CodeValidationResponse(AuthResponse):
    """Response from code validation operation."""
    token: Optional[str] = None
    user_id: Optional[str] = None


class PasswordResetResponse(AuthResponse):
    """Response from password reset operation."""
    pass


class UserUpdateResponse(AuthResponse):
    """Response from user update operation."""
    profile: Optional[Profile] = None
    requires_email_validation: bool = False
