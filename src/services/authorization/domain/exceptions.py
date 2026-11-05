"""
Custom exceptions for authentication and user management.

Provides specific exception types for different error scenarios,
enabling better error handling and user feedback.
"""


class AuthenticationError(Exception):
    """Base exception for authentication-related errors."""
    def __init__(self, message: str, code: str = None):
        self.message = message
        self.code = code
        super().__init__(self.message)


class InvalidCredentialsError(AuthenticationError):
    """Raised when login credentials are invalid."""
    def __init__(self, message: str = "Invalid email or password"):
        super().__init__(message, "INVALID_CREDENTIALS")


class UserNotFoundError(AuthenticationError):
    """Raised when a user cannot be found."""
    def __init__(self, message: str = "User not found"):
        super().__init__(message, "USER_NOT_FOUND")


class UserAlreadyExistsError(AuthenticationError):
    """Raised when attempting to create a user that already exists."""
    def __init__(self, message: str = "User already registered"):
        super().__init__(message, "USER_ALREADY_REGISTERED")


class InvalidEmailError(AuthenticationError):
    """Raised when email format is invalid."""
    def __init__(self, message: str = "Invalid email format"):
        super().__init__(message, "INVALID_EMAIL_FORMAT")


class EmailNotValidatedError(AuthenticationError):
    """Raised when user attempts to login without validating email."""
    def __init__(self, message: str = "Email validation required"):
        super().__init__(message, "VALIDATE_EMAIL")


class UserDeactivatedError(AuthenticationError):
    """Raised when user account is deactivated."""
    def __init__(self, message: str = "User account is deactivated"):
        super().__init__(message, "USER_DEACTIVATED")


class InvalidCodeError(AuthenticationError):
    """Raised when validation code is incorrect."""
    def __init__(self, message: str = "Invalid validation code", attempts_left: int = None):
        self.attempts_left = attempts_left
        if attempts_left is not None:
            message = f"{message}. {attempts_left} attempts remaining."
        super().__init__(message, "INVALID_CODE")


class TooManyAttemptsError(AuthenticationError):
    """Raised when user exceeds maximum validation attempts."""
    def __init__(self, message: str = "Too many failed attempts. Please request a new code."):
        super().__init__(message, "TOO_MANY_ATTEMPTS")


class RateLimitExceededError(AuthenticationError):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str = "Rate limit exceeded. Please try again later."):
        super().__init__(message, "RATE_LIMIT_EXCEEDED")


class InvalidStateTransitionError(AuthenticationError):
    """Raised when an invalid user state transition is attempted."""
    def __init__(self, from_state: str, to_state: str):
        message = f"Invalid state transition from {from_state} to {to_state}"
        super().__init__(message, "INVALID_STATE_TRANSITION")


class WeakPasswordError(AuthenticationError):
    """Raised when password doesn't meet complexity requirements."""
    def __init__(self, message: str = "Password does not meet security requirements"):
        super().__init__(message, "WEAK_PASSWORD")


class InvalidTokenError(AuthenticationError):
    """Raised when a token is invalid or expired."""
    def __init__(self, message: str = "Invalid or expired token"):
        super().__init__(message, "INVALID_TOKEN")
