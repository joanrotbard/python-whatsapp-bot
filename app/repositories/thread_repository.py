"""Repository for managing OpenAI thread storage using Redis (Strategy Pattern)."""
import logging
from typing import Optional
import redis

from app.config.settings import Config


class ThreadRepository:
    """
    Repository for managing thread storage using Redis.
    
    Follows Repository Pattern and Single Responsibility Principle.
    Uses Redis TTL for automatic expiration of inactive threads.
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None, ttl: Optional[int] = None):
        """
        Initialize the thread repository.
        
        Args:
            redis_client: Redis client instance (Dependency Injection)
            ttl: Time to live in seconds (defaults to Config value)
        """
        self.redis = redis_client
        self.ttl = ttl or Config.REDIS_THREAD_TTL
        self._logger = logging.getLogger(__name__)
        self._key_prefix = "thread:"
    
    def _get_key(self, wa_id: str) -> str:
        """Generate Redis key for thread ID."""
        return f"{self._key_prefix}{wa_id}"
    
    def get_thread_id(self, wa_id: str) -> Optional[str]:
        """
        Retrieve thread ID for a given WhatsApp ID.
        
        Args:
            wa_id: WhatsApp user ID
            
        Returns:
            Thread ID if exists, None otherwise
        """
        if not self.redis:
            self._logger.error("Redis client not initialized")
            return None
        
        try:
            key = self._get_key(wa_id)
            thread_id = self.redis.get(key)
            
            if thread_id:
                self._logger.debug(f"Retrieved thread {thread_id} for {wa_id}")
            else:
                self._logger.debug(f"No thread found for {wa_id}")
            
            return thread_id
        except redis.RedisError as e:
            self._logger.error(f"Error retrieving thread for {wa_id}: {e}")
            return None
    
    def save_thread_id(self, wa_id: str, thread_id: str) -> bool:
        """
        Store thread ID for a WhatsApp ID with TTL.
        
        Args:
            wa_id: WhatsApp user ID
            thread_id: OpenAI thread ID
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis:
            self._logger.error("Redis client not initialized")
            return False
        
        try:
            key = self._get_key(wa_id)
            result = self.redis.setex(key, self.ttl, thread_id)
            
            if result:
                self._logger.info(f"Saved thread {thread_id} for {wa_id} with TTL {self.ttl}s")
            else:
                self._logger.warning(f"Failed to save thread for {wa_id}")
            
            return result
        except redis.RedisError as e:
            self._logger.error(f"Error storing thread for {wa_id}: {e}")
            return False
    
    def delete_thread(self, wa_id: str) -> bool:
        """
        Delete thread for a WhatsApp ID.
        
        Args:
            wa_id: WhatsApp user ID
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis:
            self._logger.error("Redis client not initialized")
            return False
        
        try:
            key = self._get_key(wa_id)
            result = self.redis.delete(key)
            
            if result:
                self._logger.info(f"Deleted thread for {wa_id}")
            else:
                self._logger.debug(f"No thread to delete for {wa_id}")
            
            return bool(result)
        except redis.RedisError as e:
            self._logger.error(f"Error deleting thread for {wa_id}: {e}")
            return False
    
    def extend_ttl(self, wa_id: str) -> bool:
        """
        Extend TTL for an existing thread (reset expiration timer).
        
        Args:
            wa_id: WhatsApp user ID
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis:
            return False
        
        try:
            key = self._get_key(wa_id)
            return bool(self.redis.expire(key, self.ttl))
        except redis.RedisError as e:
            self._logger.error(f"Error extending TTL for {wa_id}: {e}")
            return False
    
    def get_all_threads(self) -> dict[str, str]:
        """
        Get all thread mappings (for admin/debugging purposes).
        
        Returns:
            Dictionary mapping wa_id to thread_id
        """
        if not self.redis:
            return {}
        
        try:
            pattern = f"{self._key_prefix}*"
            keys = self.redis.keys(pattern)
            
            if not keys:
                return {}
            
            # Use pipeline for better performance
            pipe = self.redis.pipeline()
            for key in keys:
                pipe.get(key)
            values = pipe.execute()
            
            # Extract wa_id from keys (remove prefix)
            result = {}
            for key, thread_id in zip(keys, values):
                wa_id = key.replace(self._key_prefix, "")
                if thread_id:
                    result[wa_id] = thread_id
            
            return result
        except redis.RedisError as e:
            self._logger.error(f"Error getting all threads: {e}")
            return {}
