"""Use case for processing incoming messages (Use Case Pattern)."""
import logging
from typing import Dict, Any

from app.domain.interfaces.message_provider import IMessageProvider
from app.domain.entities.message import Message
from app.application.services.conversation_service import (
    ConversationService,
    ConversationRequest
)
from app.utils.text_processor import WhatsAppTextProcessor


logger = logging.getLogger(__name__)


class ProcessMessageUseCase:
    """
    Use case for processing incoming messages from message providers (e.g., WhatsApp).
    
    Follows Use Case Pattern - encapsulates application-specific business logic.
    Uses ConversationService for core AI logic, keeping provider-specific concerns separate.
    """
    
    def __init__(
        self,
        message_provider: IMessageProvider,
        conversation_service: ConversationService
    ):
        """
        Initialize use case with dependencies (Dependency Injection).
        
        Args:
            message_provider: Message provider interface (WhatsApp, etc.)
            conversation_service: Core conversation service for AI interactions
        """
        self.message_provider = message_provider
        self.conversation_service = conversation_service
        self.text_processor = WhatsAppTextProcessor()
    
    def execute(self, webhook_body: Dict[str, Any]) -> None:
        """
        Execute the use case - process incoming message from webhook.
        
        This method handles provider-specific concerns (parsing webhook, sending messages)
        while delegating core AI logic to ConversationService.
        
        Args:
            webhook_body: Raw webhook payload from message provider
        """
        # Parse webhook into domain entity
        parsed_data = self.message_provider.parse_webhook(webhook_body)
        if not parsed_data:
            logger.warning("Invalid webhook payload")
            return
        
        message = Message(
            user_id=parsed_data["user_id"],
            user_name=parsed_data["user_name"],
            message_id=parsed_data["message_id"],
            message_body=parsed_data["message_body"],
            provider=parsed_data["provider"]
        )
        
        # Send typing indicator (provider-specific)
        try:
            self.message_provider.send_typing_indicator(message.message_id)
        except Exception:
            pass  # Non-critical
        
        # Use conversation service for AI response (provider-agnostic)
        conversation_request = ConversationRequest(
            user_id=message.user_id,
            user_name=message.user_name,
            message=message.message_body
        )
        
        conversation_response = self.conversation_service.process_message(conversation_request)
        
        if not conversation_response.success:
            logger.error(
                f"Failed to generate response for {message.user_id}: "
                f"{conversation_response.error}"
            )
            # Send error message to user
            error_message = conversation_response.response_text
        else:
            error_message = None
            response_text = conversation_response.response_text
        
        # Process text for provider-specific formatting
        processed_text = self.text_processor.process(
            error_message if error_message else response_text
        )
        
        # Send response via message provider
        result = self.message_provider.send_text_message(
            recipient=message.user_id,
            message=processed_text
        )
        
        if not result:
            logger.error(f"Failed to send response to {message.user_id}")
        else:
            logger.info(f"Message processed for {message.user_id}")

