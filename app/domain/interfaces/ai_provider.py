"""Interface for AI providers (Strategy Pattern).

This allows switching between different AI services:
- OpenAI
- Anthropic (Claude)
- Google Gemini
- Local LLMs
- etc.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class IAIProvider(ABC):
    """
    Interface for AI providers following Strategy Pattern.
    
    Implementations can be swapped without changing business logic.
    """
    
    @abstractmethod
    def generate_response(
        self,
        message_body: str,
        user_id: str,
        user_name: str,
        function_handler: Optional[Any] = None
    ) -> str:
        """
        Generate AI response to user message.
        
        Args:
            message_body: User's message text
            user_id: Unique user identifier
            user_name: User's display name
            function_handler: Optional handler for function calls (deprecated, kept for compatibility)
            
        Returns:
            Generated response text
            
        Raises:
            Exception: If AI service call fails
        """
        pass
    
    @abstractmethod
    def get_thread_id(self, user_id: str) -> Optional[str]:
        """
        Get conversation thread ID for user (backward compatibility).
        
        For Chat Completions API, this may return user_id directly.
        This method exists for backward compatibility.
        
        Args:
            user_id: Unique user identifier
            
        Returns:
            Conversation identifier (may be user_id or thread_id)
        """
        pass

