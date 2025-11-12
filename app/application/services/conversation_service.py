"""Core conversation service (Service Layer Pattern).

This service handles AI conversation logic independently of message providers.
Can be used by both WhatsApp webhooks and frontend API endpoints.
"""
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from app.domain.interfaces.ai_provider import IAIProvider


logger = logging.getLogger(__name__)


@dataclass
class ConversationRequest:
    """Request for conversation service."""
    user_id: str
    user_name: str
    message: str
    context: Optional[Dict[str, Any]] = None


@dataclass
class ConversationResponse:
    """Response from conversation service."""
    response_text: str
    user_id: str
    success: bool
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ConversationService:
    """
    Core conversation service that handles AI interactions.
    
    This service is provider-agnostic and can be used by:
    - WhatsApp webhooks
    - Frontend API endpoints
    - Any other integration
    
    Follows Service Layer Pattern - encapsulates business logic
    without being tied to specific delivery mechanisms.
    """
    
    def __init__(self, ai_provider: IAIProvider):
        """
        Initialize conversation service.
        
        Args:
            ai_provider: AI provider for generating responses
        """
        self.ai_provider = ai_provider
        self._logger = logging.getLogger(__name__)
    
    def process_message(self, request: ConversationRequest) -> ConversationResponse:
        """
        Process a user message and generate AI response.
        
        This is the core method that handles:
        - Conversation context management
        - AI response generation
        - Function calling (if needed)
        
        Args:
            request: Conversation request with user message
            
        Returns:
            Conversation response with AI-generated text
        """
        try:
            self._logger.info(
                f"Processing message for user {request.user_id}: "
                f"{request.message[:50]}..."
            )
            
            # Generate AI response
            # The AI provider handles:
            # - Conversation history retrieval
            # - Context management
            # - Function calling
            # - Response generation
            response_text = self.ai_provider.generate_response(
                message_body=request.message,
                user_id=request.user_id,
                user_name=request.user_name
            )
            
            return ConversationResponse(
                response_text=response_text,
                user_id=request.user_id,
                success=True,
                metadata={
                    "message_length": len(request.message),
                    "response_length": len(response_text)
                }
            )
            
        except Exception as e:
            self._logger.error(
                f"Error processing message for user {request.user_id}: {e}",
                exc_info=True
            )
            return ConversationResponse(
                response_text="I apologize, but I encountered an error processing your message. Please try again.",
                user_id=request.user_id,
                success=False,
                error=str(e)
            )
    
    def get_conversation_history(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get conversation history for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Conversation history if available, None otherwise
        """
        try:
            # Get thread/conversation ID
            thread_id = self.ai_provider.get_thread_id(user_id)
            
            if thread_id:
                return {
                    "user_id": user_id,
                    "thread_id": thread_id,
                    "has_history": True
                }
            else:
                return {
                    "user_id": user_id,
                    "thread_id": None,
                    "has_history": False
                }
        except Exception as e:
            self._logger.error(f"Error getting conversation history: {e}")
            return None

