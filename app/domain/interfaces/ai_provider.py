"""Interface for AI providers (Strategy Pattern).

This allows switching between different AI services:
- OpenAI
- Anthropic (Claude)
- Google Gemini
- Local LLMs
- etc.
"""
from abc import ABC, abstractmethod
from typing import Optional


class IAIProvider(ABC):
    """
    Interface for AI providers following Strategy Pattern.
    
    Implementations can be swapped without changing business logic.
    """
    
    @abstractmethod
    def generate_response(self, message_body: str, user_id: str, user_name: str) -> str:
        """
        Generate AI response to user message.
        
        Args:
            message_body: User's message text
            user_id: Unique user identifier
            user_name: User's display name
            
        Returns:
            Generated response text
            
        Raises:
            Exception: If AI service call fails
        """
        pass
    
    @abstractmethod
    def get_thread_id(self, user_id: str) -> Optional[str]:
        """
        Get conversation thread ID for user.
        
        Args:
            user_id: Unique user identifier
            
        Returns:
            Thread ID if exists, None otherwise
        """
        pass

