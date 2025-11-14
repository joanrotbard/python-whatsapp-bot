"""Redis-based session storage implementation."""
import logging
import json
from typing import Optional, Dict, Any
import redis

from app.domain.interfaces.session_storage import ISessionStorage
from app.config.settings import Config
from app.infrastructure.redis_client import RedisClientFactory


class RedisSessionStorage(ISessionStorage):
    """
    Redis-based session storage implementation.
    
    Follows Repository Pattern and Single Responsibility Principle.
    Uses Redis for persistent session storage with TTL support.
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None, ttl: Optional[int] = None):
        """
        Initialize the session storage.
        
        Args:
            redis_client: Redis client instance (Dependency Injection)
            ttl: Default time to live in seconds (defaults to 24 hours = 86400s)
        """
        self.redis = redis_client or RedisClientFactory.get_client()
        self.default_ttl = ttl or 86400  # 24 hours default
        self._logger = logging.getLogger(__name__)
        self._key_prefix = "session:"
    
    def _get_key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"{self._key_prefix}{session_id}"
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data from Redis."""
        if not self.redis:
            self._logger.warning("Redis not available - cannot retrieve session")
            return None
        
        try:
            key = self._get_key(session_id)
            data = self.redis.get(key)
            
            if data is None:
                return None
            
            return json.loads(data)
        except Exception as e:
            self._logger.error(f"Failed to get session {session_id}: {e}")
            return None
    
    def set_session(self, session_id: str, data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """Store session data in Redis."""
        if not self.redis:
            self._logger.warning("Redis not available - cannot store session")
            raise RuntimeError("Redis not available - cannot store session")
        
        try:
            key = self._get_key(session_id)
            ttl = ttl or self.default_ttl
            
            serialized = json.dumps(data)
            self.redis.setex(key, ttl, serialized)
            self._logger.debug(f"Session {session_id} stored with TTL {ttl}s")
        except Exception as e:
            self._logger.error(f"Failed to set session {session_id}: {e}")
            raise
    
    def delete_session(self, session_id: str) -> None:
        """Delete session data from Redis."""
        if not self.redis:
            self._logger.warning("Redis not available - cannot delete session")
            return
        
        try:
            key = self._get_key(session_id)
            self.redis.delete(key)
            self._logger.debug(f"Session {session_id} deleted")
        except Exception as e:
            self._logger.error(f"Failed to delete session {session_id}: {e}")
            raise
    
    def update_session(self, session_id: str, updates: Dict[str, Any]) -> None:
        """Update session data (partial update)."""
        if not self.redis:
            self._logger.warning("Redis not available - cannot update session")
            raise RuntimeError("Redis not available - cannot update session")
        
        try:
            current = self.get_session(session_id)
            if current is None:
                raise ValueError(f"Session {session_id} not found")
            
            current.update(updates)
            # Get current TTL to preserve it
            key = self._get_key(session_id)
            ttl = self.redis.ttl(key)
            if ttl > 0:
                self.set_session(session_id, current, ttl=ttl)
            else:
                self.set_session(session_id, current)
        except Exception as e:
            self._logger.error(f"Failed to update session {session_id}: {e}")
            raise

