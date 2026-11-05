"""
Rate limiting for authentication operations.

Provides protection against brute force attacks on login and validation endpoints.
"""

from typing import Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import threading


class RateLimiter:
    """
    Simple in-memory rate limiter for authentication operations.
    
    For production use, consider using Redis-backed rate limiting.
    """
    
    def __init__(
        self,
        max_attempts: int = 5,
        window_minutes: int = 15,
        lockout_minutes: int = 30
    ):
        """
        Initialize rate limiter.
        
        Args:
            max_attempts: Maximum attempts allowed within window
            window_minutes: Time window in minutes for counting attempts
            lockout_minutes: How long to lock out after exceeding max attempts
        """
        self.max_attempts = max_attempts
        self.window = timedelta(minutes=window_minutes)
        self.lockout_duration = timedelta(minutes=lockout_minutes)
        
        # Store attempts: {key: [(timestamp1, timestamp2, ...)]}
        self._attempts: Dict[str, list] = defaultdict(list)
        
        # Store lockouts: {key: lockout_until_timestamp}
        self._lockouts: Dict[str, datetime] = {}
        
        # Thread lock for thread-safe operations
        self._lock = threading.Lock()
    
    def _clean_old_attempts(self, key: str) -> None:
        """Remove attempts outside the current time window."""
        now = datetime.utcnow()
        cutoff = now - self.window
        
        if key in self._attempts:
            self._attempts[key] = [
                attempt_time for attempt_time in self._attempts[key]
                if attempt_time > cutoff
            ]
    
    def is_locked_out(self, key: str) -> bool:
        """
        Check if a key is currently locked out.
        
        Args:
            key: Identifier to check (email, IP, user_id, etc.)
            
        Returns:
            True if currently locked out, False otherwise
        """
        with self._lock:
            if key in self._lockouts:
                if datetime.utcnow() < self._lockouts[key]:
                    return True
                else:
                    # Lockout expired, remove it
                    del self._lockouts[key]
                    if key in self._attempts:
                        del self._attempts[key]
            return False
    
    def get_remaining_attempts(self, key: str) -> int:
        """
        Get number of remaining attempts before lockout.
        
        Args:
            key: Identifier to check
            
        Returns:
            Number of attempts remaining (0 if locked out)
        """
        if self.is_locked_out(key):
            return 0
        
        with self._lock:
            self._clean_old_attempts(key)
            current_attempts = len(self._attempts[key])
            return max(0, self.max_attempts - current_attempts)
    
    def record_attempt(self, key: str) -> bool:
        """
        Record an attempt and check if limit is exceeded.
        
        Args:
            key: Identifier to track (email, IP, user_id, etc.)
            
        Returns:
            True if attempt is allowed, False if rate limit exceeded
        """
        if self.is_locked_out(key):
            return False
        
        with self._lock:
            self._clean_old_attempts(key)
            
            # Add current attempt
            self._attempts[key].append(datetime.utcnow())
            
            # Check if limit exceeded
            if len(self._attempts[key]) > self.max_attempts:
                # Lock out the key
                self._lockouts[key] = datetime.utcnow() + self.lockout_duration
                return False
            
            return True
    
    def reset(self, key: str) -> None:
        """
        Reset attempts for a key (e.g., after successful login).
        
        Args:
            key: Identifier to reset
        """
        with self._lock:
            if key in self._attempts:
                del self._attempts[key]
            if key in self._lockouts:
                del self._lockouts[key]
    
    def get_lockout_time_remaining(self, key: str) -> Optional[timedelta]:
        """
        Get remaining lockout time for a key.
        
        Args:
            key: Identifier to check
            
        Returns:
            Time remaining in lockout, or None if not locked out
        """
        with self._lock:
            if key in self._lockouts:
                remaining = self._lockouts[key] - datetime.utcnow()
                if remaining.total_seconds() > 0:
                    return remaining
        return None


# Global rate limiters for different operations
login_rate_limiter = RateLimiter(max_attempts=5, window_minutes=15, lockout_minutes=30)
code_validation_rate_limiter = RateLimiter(max_attempts=3, window_minutes=10, lockout_minutes=60)
password_reset_rate_limiter = RateLimiter(max_attempts=3, window_minutes=60, lockout_minutes=120)
