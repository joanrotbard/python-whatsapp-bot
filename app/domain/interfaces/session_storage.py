"""Interface for session storage (Repository Pattern)."""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class ISessionStorage(ABC):
    """Interface for storing and retrieving session data."""
    
    @abstractmethod
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Session data dictionary or None if not found
        """
        pass
    
    @abstractmethod
    def set_session(self, session_id: str, data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """
        Store session data.
        
        Args:
            session_id: Unique session identifier
            data: Session data dictionary
            ttl: Optional time to live in seconds
        """
        pass
    
    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        """
        Delete session data.
        
        Args:
            session_id: Unique session identifier
        """
        pass
    
    @abstractmethod
    def update_session(self, session_id: str, updates: Dict[str, Any]) -> None:
        """
        Update session data (partial update).
        
        Args:
            session_id: Unique session identifier
            updates: Dictionary with fields to update
        """
        pass

