"""Interface for message providers (Strategy Pattern).

This allows switching between different messaging platforms:
- WhatsApp
- Telegram
- SMS
- Email
- etc.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class IMessageProvider(ABC):
    """
    Interface for message providers following Strategy Pattern.
    
    Implementations can be swapped without changing business logic.
    """
    
    @abstractmethod
    def send_text_message(self, recipient: str, message: str) -> Optional[Dict[str, Any]]:
        """
        Send a text message to a recipient.
        
        Args:
            recipient: Recipient identifier (phone number, user ID, etc.)
            message: Message text content
            
        Returns:
            Response dictionary with status and message_id, or None if failed
        """
        pass
    
    @abstractmethod
    def send_typing_indicator(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Send typing indicator to show the bot is processing.
        
        Args:
            message_id: Original message ID to respond to
            
        Returns:
            Response dictionary, or None if failed
        """
        pass
    
    @abstractmethod
    def parse_webhook(self, webhook_body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse incoming webhook payload into standardized format.
        
        Args:
            webhook_body: Raw webhook payload from provider
            
        Returns:
            Parsed message data with keys: wa_id, name, message_id, message_body
            or None if not a valid message
        """
        pass

