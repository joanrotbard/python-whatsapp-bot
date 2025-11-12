"""Interface for thread repository (Repository Pattern)."""
from abc import ABC, abstractmethod
from typing import Optional


class IThreadRepository(ABC):
    """
    Interface for thread storage following Repository Pattern.
    
    Allows switching storage backends (Redis, PostgreSQL, MongoDB, etc.)
    without changing business logic.
    """
    
    @abstractmethod
    def get_thread_id(self, user_id: str) -> Optional[str]:
        """
        Retrieve thread ID for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Thread ID if exists, None otherwise
        """
        pass
    
    @abstractmethod
    def save_thread_id(self, user_id: str, thread_id: str) -> bool:
        """
        Store thread ID for a user.
        
        Args:
            user_id: User identifier
            thread_id: Thread ID to store
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def delete_thread(self, user_id: str) -> bool:
        """
        Delete thread for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def extend_ttl(self, user_id: str) -> bool:
        """
        Extend time-to-live for thread.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if successful, False otherwise
        """
        pass

