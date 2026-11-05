"""
Token Blacklist Service for managing revoked JWT tokens.

Provides in-memory token blacklist with automatic expiration cleanup.
For production, consider using Redis for distributed blacklist.
"""

import logging
from typing import Set, Dict
from datetime import datetime, timedelta
import threading
import time

logger = logging.getLogger(__name__)


class TokenBlacklist:
    """
    Manages blacklisted (revoked) JWT tokens.
    
    Uses in-memory storage with automatic cleanup of expired entries.
    For production with multiple servers, use Redis-backed implementation.
    """
    
    def __init__(self, cleanup_interval_minutes: int = 60):
        """
        Initialize token blacklist.
        
        Args:
            cleanup_interval_minutes: How often to clean up expired tokens
        """
        # Store token hash -> expiration timestamp
        self._blacklist: Dict[str, datetime] = {}
        self._lock = threading.Lock()
        self.cleanup_interval = timedelta(minutes=cleanup_interval_minutes)
        
        # Start cleanup thread
        self._start_cleanup_thread()
        
        logger.info("TokenBlacklist initialized")
    
    def blacklist_token(self, token_jti: str, expires_at: datetime) -> None:
        """
        Add a token to the blacklist.
        
        Args:
            token_jti: Token JTI (unique identifier) or hash
            expires_at: When the token would naturally expire
        """
        with self._lock:
            self._blacklist[token_jti] = expires_at
            logger.info(f"Token blacklisted: {token_jti[:10]}...")
    
    def is_blacklisted(self, token_jti: str) -> bool:
        """
        Check if a token is blacklisted.
        
        Args:
            token_jti: Token JTI or hash to check
            
        Returns:
            True if token is blacklisted and not yet expired
        """
        with self._lock:
            if token_jti not in self._blacklist:
                return False
            
            # Check if blacklist entry has expired
            if datetime.utcnow() > self._blacklist[token_jti]:
                # Token expiry passed, remove from blacklist
                del self._blacklist[token_jti]
                return False
            
            return True
    
    def cleanup_expired(self) -> int:
        """
        Remove expired tokens from blacklist.
        
        Returns:
            Number of tokens removed
        """
        now = datetime.utcnow()
        removed = 0
        
        with self._lock:
            expired_tokens = [
                jti for jti, expires_at in self._blacklist.items()
                if now > expires_at
            ]
            
            for jti in expired_tokens:
                del self._blacklist[jti]
                removed += 1
        
        if removed > 0:
            logger.info(f"Cleaned up {removed} expired blacklist entries")
        
        return removed
    
    def get_blacklist_size(self) -> int:
        """
        Get current number of blacklisted tokens.
        
        Returns:
            Number of tokens in blacklist
        """
        with self._lock:
            return len(self._blacklist)
    
    def clear_all(self) -> None:
        """Clear all blacklisted tokens (for testing)."""
        with self._lock:
            count = len(self._blacklist)
            self._blacklist.clear()
            logger.warning(f"Cleared all {count} blacklist entries")
    
    def _start_cleanup_thread(self) -> None:
        """Start background thread for automatic cleanup."""
        def cleanup_loop():
            while True:
                time.sleep(self.cleanup_interval.total_seconds())
                try:
                    self.cleanup_expired()
                except Exception as e:
                    logger.error(f"Error in cleanup thread: {e}")
        
        thread = threading.Thread(target=cleanup_loop, daemon=True)
        thread.start()
        logger.info("Cleanup thread started")


# Global singleton instance
_token_blacklist: TokenBlacklist = None


def get_token_blacklist() -> TokenBlacklist:
    """
    Get or create the global TokenBlacklist instance.
    
    Returns:
        Global TokenBlacklist instance
    """
    global _token_blacklist
    if _token_blacklist is None:
        _token_blacklist = TokenBlacklist()
    return _token_blacklist


# For production, consider Redis-backed implementation:
"""
class RedisTokenBlacklist:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    def blacklist_token(self, token_jti: str, expires_at: datetime):
        # Calculate TTL in seconds
        ttl = int((expires_at - datetime.utcnow()).total_seconds())
        if ttl > 0:
            # Set key with expiration
            self.redis.setex(f"blacklist:{token_jti}", ttl, "1")
    
    def is_blacklisted(self, token_jti: str) -> bool:
        return self.redis.exists(f"blacklist:{token_jti}")
"""
