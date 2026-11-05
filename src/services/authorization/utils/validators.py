"""
Input validators for authentication and user management.

Provides validation functions for emails, passwords, and other user inputs.
"""

import re
from typing import List
from services.authorization.domain.exceptions import InvalidEmailError, WeakPasswordError


class EmailValidator:
    """Validates email addresses."""
    
    # Disposable email domains to block
    DISPOSABLE_DOMAINS = {
        'tempmail.com', 'throwaway.email', 'guerrillamail.com',
        '10minutemail.com', 'mailinator.com', 'trashmail.com'
    }
    
    @staticmethod
    def validate(email: str, allow_disposable: bool = False) -> str:
        """
        Validate email format and optionally check for disposable domains.
        
        Args:
            email: Email address to validate
            allow_disposable: If False, rejects known disposable email domains
            
        Returns:
            Lowercase normalized email address
            
        Raises:
            InvalidEmailError: If email format is invalid or from disposable domain
        """
        if not email:
            raise InvalidEmailError("Email is required")
        
        # Normalize email
        email = email.strip().lower()
        
        # Validate format
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise InvalidEmailError(f"Invalid email format: {email}")
        
        # Check for disposable domains
        if not allow_disposable:
            domain = email.split('@')[1]
            if domain in EmailValidator.DISPOSABLE_DOMAINS:
                raise InvalidEmailError(f"Disposable email addresses are not allowed")
        
        return email


class PasswordValidator:
    """Validates password strength."""
    
    MIN_LENGTH = 8
    MAX_LENGTH = 128
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = True
    
    # Common weak passwords to reject
    COMMON_PASSWORDS = {
        'password', '12345678', 'qwerty', 'abc123', 'password123',
        'admin', 'letmein', 'welcome', '123456', 'password1'
    }
    
    @staticmethod
    def validate(password: str, user_email: str = None) -> None:
        """
        Validate password meets security requirements.
        
        Args:
            password: Password to validate
            user_email: Optional user email to check password doesn't contain email parts
            
        Raises:
            WeakPasswordError: If password doesn't meet requirements
        """
        if not password:
            raise WeakPasswordError("Password is required")
        
        errors: List[str] = []
        
        # Check length
        if len(password) < PasswordValidator.MIN_LENGTH:
            errors.append(f"Password must be at least {PasswordValidator.MIN_LENGTH} characters")
        
        if len(password) > PasswordValidator.MAX_LENGTH:
            errors.append(f"Password must not exceed {PasswordValidator.MAX_LENGTH} characters")
        
        # Check complexity
        if PasswordValidator.REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        if PasswordValidator.REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        if PasswordValidator.REQUIRE_DIGIT and not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")
        
        if PasswordValidator.REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character")
        
        # Check against common passwords
        if password.lower() in PasswordValidator.COMMON_PASSWORDS:
            errors.append("Password is too common. Please choose a stronger password")
        
        # Check password doesn't contain email
        if user_email:
            email_parts = user_email.split('@')[0].lower().split('.')
            for part in email_parts:
                if len(part) > 3 and part in password.lower():
                    errors.append("Password should not contain parts of your email address")
                    break
        
        if errors:
            raise WeakPasswordError("; ".join(errors))
    
    @staticmethod
    def generate_validation_code(length: int = 6) -> str:
        """
        Generate a secure random validation code.
        
        Args:
            length: Length of code (default 6)
            
        Returns:
            Random numeric code as string
        """
        import secrets
        # Generate cryptographically secure random code
        code = ''.join(str(secrets.randbelow(10)) for _ in range(length))
        return code


class PhoneValidator:
    """Validates phone numbers."""
    
    @staticmethod
    def validate(phone: str) -> str:
        """
        Validate and normalize phone number.
        
        Args:
            phone: Phone number to validate
            
        Returns:
            Normalized phone number
            
        Raises:
            ValueError: If phone format is invalid
        """
        if not phone:
            return ""
        
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)
        
        # Basic validation - should have at least 10 digits
        if len(digits) < 10 or len(digits) > 15:
            raise ValueError("Phone number must be between 10 and 15 digits")
        
        return f"+{digits}"
