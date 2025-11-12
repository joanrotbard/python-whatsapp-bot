"""WhatsApp provider implementation (Strategy Pattern)."""
import logging
from typing import Optional, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.domain.interfaces.message_provider import IMessageProvider
from app.config.settings import Config
from app.utils.webhook_parser import WebhookParser


class WhatsAppProvider(IMessageProvider):
    """
    WhatsApp Cloud API provider implementation.
    
    Implements IMessageProvider interface following Strategy Pattern.
    """
    
    def __init__(self):
        """Initialize WhatsApp provider with connection pooling."""
        self._logger = logging.getLogger(__name__)
        self._session = self._create_session()
        self._base_url = None
        self._headers = None
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with connection pooling."""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,
            pool_maxsize=20,
            pool_block=False
        )
        
        session.mount("https://", adapter)
        return session
    
    def _get_base_url(self) -> str:
        """Get the base URL for WhatsApp API."""
        if not self._base_url:
            version = Config.VERSION
            phone_number_id = Config.PHONE_NUMBER_ID
            if not phone_number_id:
                raise ValueError("PHONE_NUMBER_ID not configured")
            self._base_url = f"https://graph.facebook.com/{version}/{phone_number_id}/messages"
        return self._base_url
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        if not self._headers:
            access_token = Config.ACCESS_TOKEN
            if not access_token:
                raise ValueError("ACCESS_TOKEN not configured")
            self._headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            }
        return self._headers
    
    def send_text_message(self, recipient: str, message: str) -> Optional[Dict[str, Any]]:
        """
        Send a text message via WhatsApp API.
        
        Args:
            recipient: Phone number (with or without + prefix)
            message: Message text
            
        Returns:
            Response dictionary with status and message_id, or None if failed
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient.strip(),
            "type": "text",
            "text": {"preview_url": False, "body": message}
        }
        
        try:
            url = self._get_base_url()
            headers = self._get_headers()
            
            response = self._session.post(
                url,
                json=payload,
                headers=headers,
                timeout=8
            )
            
            if response.status_code == 200:
                response_data = response.json()
                return {
                    "status": "success",
                    "message_id": response_data.get("messages", [{}])[0].get("id"),
                    "response": response_data
                }
            else:
                self._log_error(response)
                # Return error dictionary instead of None
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', 'Unknown error')
                    error_code = error_data.get('error', {}).get('code')
                except:
                    error_msg = response.text or 'Unknown error'
                    error_code = None
                
                return {
                    "status": "error",
                    "error_message": error_msg,
                    "error_code": error_code,
                    "http_status": response.status_code
                }
                
        except requests.Timeout:
            self._logger.error("Request timeout")
            return None
        except requests.RequestException as e:
            self._logger.error(f"Request failed: {e}")
            return None
        except Exception as e:
            self._logger.error(f"Unexpected error: {e}", exc_info=True)
            return None
    
    def send_typing_indicator(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Send typing indicator for a message.
        
        Args:
            message_id: WhatsApp message ID
            
        Returns:
            Response dictionary, or None if failed
        """
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
            "typing_indicator": {"type": "text"}
        }
        
        try:
            url = self._get_base_url()
            headers = self._get_headers()
            
            response = self._session.post(
                url,
                json=payload,
                headers=headers,
                timeout=8
            )
            
            if response.status_code == 200:
                return {"status": "success"}
            else:
                return None
                
        except Exception:
            return None
    
    def parse_webhook(self, webhook_body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse incoming WhatsApp webhook payload.
        
        Args:
            webhook_body: Raw WhatsApp webhook payload
            
        Returns:
            Parsed message data with keys: user_id, user_name, message_id, message_body
            or None if not a valid message
        """
        if not WebhookParser.is_valid_message(webhook_body):
            return None
        
        try:
            value = webhook_body["entry"][0]["changes"][0]["value"]
            message = value["messages"][0]
            
            # Extract user info
            try:
                contact = value["contacts"][0]
                user_id = contact["wa_id"]
                user_name = contact.get("profile", {}).get("name", user_id)
            except (KeyError, IndexError):
                user_id = message.get("from", "unknown")
                user_name = user_id
            
            return {
                "user_id": user_id,
                "user_name": user_name,
                "message_id": message["id"],
                "message_body": message["text"]["body"],
                "provider": "whatsapp"
            }
        except (KeyError, IndexError) as e:
            self._logger.error(f"Error parsing webhook: {e}")
            return None
    
    def _log_error(self, response: requests.Response) -> None:
        """Log error response details."""
        try:
            error_data = response.json()
            error_msg = error_data.get('error', {}).get('message', 'Unknown error')
            error_code = error_data.get('error', {}).get('code')
            self._logger.error(
                f"HTTP {response.status_code} error: {error_msg} (code: {error_code})"
            )
        except:
            self._logger.error(f"HTTP {response.status_code} error: {response.text}")

