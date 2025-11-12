"""Use case for processing incoming messages (Use Case Pattern)."""
import logging
from typing import Dict, Any

from app.domain.interfaces.message_provider import IMessageProvider
from app.domain.interfaces.ai_provider import IAIProvider
from app.domain.entities.message import Message
from app.utils.text_processor import WhatsAppTextProcessor


logger = logging.getLogger(__name__)


class ProcessMessageUseCase:
    """
    Use case for processing incoming messages.
    
    Follows Use Case Pattern - encapsulates application-specific business logic.
    Depends on abstractions (interfaces) not concrete implementations.
    """
    
    def __init__(
        self,
        message_provider: IMessageProvider,
        ai_provider: IAIProvider
    ):
        """
        Initialize use case with dependencies (Dependency Injection).
        
        Args:
            message_provider: Message provider interface
            ai_provider: AI provider interface
        """
        self.message_provider = message_provider
        self.ai_provider = ai_provider
        self.text_processor = WhatsAppTextProcessor()
    
    def execute(self, webhook_body: Dict[str, Any]) -> None:
        """
        Execute the use case - process incoming message.
        
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
        
        # Send typing indicator
        try:
            self.message_provider.send_typing_indicator(message.message_id)
        except Exception:
            pass  # Non-critical
        
        # Generate AI response
        response_text = self.ai_provider.generate_response(
            message_body=message.message_body,
            user_id=message.user_id,
            user_name=message.user_name
        )
        
        # Process text for provider-specific formatting
        processed_text = self.text_processor.process(response_text)
        
        # Send response
        result = self.message_provider.send_text_message(
            recipient=message.user_id,
            message=processed_text
        )
        
        if not result:
            logger.error(f"Failed to send response to {message.user_id}")
        else:
            logger.info(f"Message processed for {message.user_id}")

