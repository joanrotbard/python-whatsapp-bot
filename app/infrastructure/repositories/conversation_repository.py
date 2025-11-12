"""Repository for managing conversation history using Redis (Repository Pattern)."""
import logging
import json
from typing import Optional, List, Dict, Any
import redis

from app.domain.interfaces.conversation_repository import IConversationRepository
from app.config.settings import Config


class RedisConversationRepository(IConversationRepository):
    """
    Repository for managing conversation history using Redis.
    
    Follows Repository Pattern and Single Responsibility Principle.
    Uses Redis TTL for automatic expiration of inactive conversations (1 hour).
    Stores messages as JSON arrays.
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None, ttl: Optional[int] = None):
        """
        Initialize the conversation repository.
        
        Args:
            redis_client: Redis client instance (Dependency Injection)
            ttl: Time to live in seconds (defaults to 1 hour = 3600s)
        """
        self.redis = redis_client
        self.ttl = ttl or Config.REDIS_THREAD_TTL  # Reuse same TTL config
        self._logger = logging.getLogger(__name__)
        self._key_prefix = "conversation:"
    
    def _get_key(self, user_id: str) -> str:
        """Generate Redis key for conversation."""
        return f"{self._key_prefix}{user_id}"
    
    def get_conversation(self, user_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve conversation history for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of messages in OpenAI format, or None if no conversation exists
        """
        if not self.redis:
            self._logger.error("Redis client not initialized")
            return None
        
        try:
            key = self._get_key(user_id)
            data = self.redis.get(key)
            
            if data:
                messages = json.loads(data)
                self._logger.debug(f"Retrieved {len(messages)} messages for {user_id}")
                return messages
            else:
                self._logger.debug(f"No conversation found for {user_id}")
                return None
        except (redis.RedisError, json.JSONDecodeError) as e:
            self._logger.error(f"Error retrieving conversation for {user_id}: {e}")
            return None
    
    def save_conversation(
        self,
        user_id: str,
        messages: List[Dict[str, Any]]
    ) -> bool:
        """
        Store conversation history for a user.
        
        Args:
            user_id: User identifier
            messages: List of messages in OpenAI format
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis:
            self._logger.error("Redis client not initialized")
            return False
        
        try:
            key = self._get_key(user_id)
            data = json.dumps(messages)
            result = self.redis.setex(key, self.ttl, data)
            
            if result:
                self._logger.info(
                    f"Saved {len(messages)} messages for {user_id} with TTL {self.ttl}s"
                )
            else:
                self._logger.warning(f"Failed to save conversation for {user_id}")
            
            return result
        except (redis.RedisError, (TypeError, ValueError)) as e:
            self._logger.error(f"Error storing conversation for {user_id}: {e}")
            return False
    
    def add_message(
        self,
        user_id: str,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_call_id: Optional[str] = None,
        name: Optional[str] = None
    ) -> bool:
        """
        Add a message to the conversation history.
        
        Args:
            user_id: User identifier
            role: Message role (user, assistant, system, tool)
            content: Message content
            tool_calls: Optional tool calls (for assistant messages)
            tool_call_id: Optional tool call ID (for tool messages)
            name: Optional function name (for tool messages)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis:
            self._logger.error("Redis client not initialized")
            return False
        
        try:
            # Get existing conversation
            messages = self.get_conversation(user_id) or []
            
            # Build message dict
            message: Dict[str, Any] = {
                "role": role,
                "content": content
            }
            
            if tool_calls:
                message["tool_calls"] = tool_calls
            
            if tool_call_id:
                message["tool_call_id"] = tool_call_id
            
            if name:
                message["name"] = name
            
            # Add message
            messages.append(message)
            
            # Save back to Redis
            return self.save_conversation(user_id, messages)
            
        except Exception as e:
            self._logger.error(f"Error adding message for {user_id}: {e}")
            return False
    
    def delete_conversation(self, user_id: str) -> bool:
        """
        Delete conversation for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis:
            self._logger.error("Redis client not initialized")
            return False
        
        try:
            key = self._get_key(user_id)
            result = self.redis.delete(key)
            
            if result:
                self._logger.info(f"Deleted conversation for {user_id}")
            else:
                self._logger.debug(f"No conversation to delete for {user_id}")
            
            return bool(result)
        except redis.RedisError as e:
            self._logger.error(f"Error deleting conversation for {user_id}: {e}")
            return False
    
    def extend_ttl(self, user_id: str) -> bool:
        """
        Extend TTL for an existing conversation (reset expiration timer).
        
        Args:
            user_id: User identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis:
            return False
        
        try:
            key = self._get_key(user_id)
            return bool(self.redis.expire(key, self.ttl))
        except redis.RedisError as e:
            self._logger.error(f"Error extending TTL for {user_id}: {e}")
            return False
    
    def clear_old_messages(self, user_id: str, keep_last_n: int = 20) -> bool:
        """
        Clear old messages, keeping only the last N messages.
        
        Useful for managing context window size.
        
        Args:
            user_id: User identifier
            keep_last_n: Number of recent messages to keep
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis:
            self._logger.error("Redis client not initialized")
            return False
        
        try:
            messages = self.get_conversation(user_id)
            if not messages:
                return True  # Nothing to clear
            
            if len(messages) <= keep_last_n:
                return True  # Already within limit
            
            # Keep system messages (if any) and last N messages
            system_messages = [msg for msg in messages if msg.get("role") == "system"]
            other_messages = [msg for msg in messages if msg.get("role") != "system"]
            
            # Keep last N of non-system messages
            recent_messages = other_messages[-keep_last_n:]
            
            # Combine: system messages first, then recent messages
            new_messages = system_messages + recent_messages
            
            self._logger.info(
                f"Cleared old messages for {user_id}: "
                f"{len(messages)} -> {len(new_messages)} messages"
            )
            
            return self.save_conversation(user_id, new_messages)
            
        except Exception as e:
            self._logger.error(f"Error clearing old messages for {user_id}: {e}")
            return False

