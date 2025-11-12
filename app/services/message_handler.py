"""Message handler service (Adapter Pattern - backward compatibility).

This is a compatibility layer that adapts the new use case pattern
to the existing MessageHandler interface.
"""
import logging
from typing import Dict, Any

from app.application.use_cases.process_message_use_case import ProcessMessageUseCase


class MessageHandler:
    """
    Message handler adapter for backward compatibility.
    
    Adapts ProcessMessageUseCase to existing MessageHandler interface.
    Follows Adapter Pattern.
    """
    
    def __init__(self, use_case: ProcessMessageUseCase):
        """
        Initialize message handler with use case.
        
        Args:
            use_case: ProcessMessageUseCase instance
        """
        self.use_case = use_case
        self._logger = logging.getLogger(__name__)
    
    def process_incoming_message(self, webhook_body: Dict[str, Any]) -> None:
        """
        Process an incoming message (delegates to use case).
        
        Args:
            webhook_body: Webhook payload
        """
        try:
            self.use_case.execute(webhook_body)
        except Exception as e:
            self._logger.error(f"Error processing message: {e}", exc_info=True)

