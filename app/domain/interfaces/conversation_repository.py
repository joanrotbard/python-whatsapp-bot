"""Interface for conversation repository (Repository Pattern).

Stores conversation history (message arrays) instead of thread IDs.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class IConversationRepository(ABC):
    """
    Interface for conversation storage following Repository Pattern.
    
    Stores message history for maintaining context in Chat Completions API.
    Allows switching storage backends (Redis, PostgreSQL, MongoDB, etc.)
    without changing business logic.
    """
    
    @abstractmethod
    def get_conversation(self, user_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve conversation history for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of messages in OpenAI format, or None if no conversation exists
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def delete_conversation(self, user_id: str) -> bool:
        """
        Delete conversation for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def extend_ttl(self, user_id: str) -> bool:
        """
        Extend time-to-live for conversation.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
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
        pass

