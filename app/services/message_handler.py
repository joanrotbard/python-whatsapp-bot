"""Message handler service coordinating WhatsApp and OpenAI services."""
import logging
from typing import Dict, Any

from app.services.whatsapp_service import WhatsAppService
from app.services.openai_service import OpenAIService
from app.utils.text_processor import WhatsAppTextProcessor


class MessageHandler:
    """Service for handling incoming WhatsApp messages."""
    
    def __init__(
        self,
        whatsapp_service: WhatsAppService,
        openai_service: OpenAIService
    ):
        """
        Initialize message handler.
        
        Args:
            whatsapp_service: WhatsApp API service
            openai_service: OpenAI service
        """
        self.whatsapp_service = whatsapp_service
        self.openai_service = openai_service
        self.text_processor = WhatsAppTextProcessor()
        self._logger = logging.getLogger(__name__)
    
    def process_incoming_message(self, webhook_body: Dict[str, Any]) -> None:
        """
        Process an incoming WhatsApp message.
        
        Args:
            webhook_body: WhatsApp webhook payload
        """
        try:
            # Extract message data
            value = webhook_body["entry"][0]["changes"][0]["value"]
            message = value["messages"][0]
            
            # Extract wa_id - try contacts first, fallback to message.from
            try:
                contact = value["contacts"][0]
                wa_id = contact["wa_id"]
                name = contact.get("profile", {}).get("name", wa_id)
            except (KeyError, IndexError):
                wa_id = message.get("from", "unknown")
                name = wa_id
            
            message_id = message["id"]
            message_body = message["text"]["body"]
            
            # Send typing indicator
            self._send_typing_indicator(message_id, wa_id)
            
            # Generate response
            response_text = self.openai_service.generate_response(message_body, wa_id, name)
            
            # Process and send response
            processed_text = self.text_processor.process(response_text)
            self._send_response(wa_id, processed_text)
            
            self._logger.info(f"Message processed for {wa_id}")
            
        except KeyError as e:
            self._logger.error(f"KeyError processing message - missing field in webhook: {e}", exc_info=True)
            self._logger.error(f"Webhook body structure: {list(webhook_body.keys())}")
        except Exception as e:
            self._logger.error(f"Error processing message: {e}", exc_info=True)
            # Don't raise - return success to WhatsApp to prevent retries
    
    def _send_typing_indicator(self, message_id: str, wa_id: str) -> None:
        """Send typing indicator."""
        try:
            self.whatsapp_service.send_typing_indicator(message_id)
        except Exception:
            pass  # Non-critical, continue processing
    
    def _send_response(self, wa_id: str, response_text: str) -> None:
        """Send response message."""
        try:
            response = self.whatsapp_service.send_text_message(wa_id, response_text)
            
            if response is None:
                self._logger.error(f"Failed to send response to {wa_id}: Connection error")
            elif response.status_code != 200:
                self._handle_send_error(response, wa_id)
                
        except Exception as e:
            self._logger.error(f"Error sending response to {wa_id}: {e}", exc_info=True)
    
    def _handle_send_error(self, response, wa_id: str) -> None:
        """Handle error when sending message."""
        error_code = None
        try:
            error_data = response.json()
            error_msg = error_data.get('error', {}).get('message', 'Unknown error')
            error_code = error_data.get('error', {}).get('code')
            
            if error_code == 131030 or 'not in allowed list' in error_msg.lower():
                self._logger.error(f"Number {wa_id} not in allowed list - add to Meta App Dashboard")
            else:
                self._logger.error(f"Failed to send to {wa_id}: {error_msg}")
        except:
            self._logger.error(f"Failed to send to {wa_id}: HTTP {response.status_code}")

