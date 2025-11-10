"""WhatsApp API service with connection pooling and error handling."""
import logging
import json
from typing import Optional, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config.settings import Config


class WhatsAppService:
    """Service for interacting with WhatsApp Cloud API."""
    
    def __init__(self):
        """Initialize WhatsApp service with connection pooling."""
        self._logger = logging.getLogger(__name__)
        self._session = self._create_session()
        self._base_url = None
        self._headers = None
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with connection pooling and retry strategy."""
        session = requests.Session()
        
        # Retry strategy for transient errors
        # Reduced retries and backoff for faster failures
        retry_strategy = Retry(
            total=2,  # Reduced from 3 for faster failure detection
            backoff_factor=0.5,  # Reduced from 1 for faster retries
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        
        # Increased pool size for better concurrency
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,  # Increased from 10
            pool_maxsize=20,  # Increased from 10
            pool_block=False  # Don't block if pool is full
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
    
    def send_text_message(self, recipient: str, message: str) -> Optional[requests.Response]:
        """
        Send a text message via WhatsApp API.
        
        Args:
            recipient: Phone number (with or without + prefix)
            message: Message text
            
        Returns:
            Response object if successful, None otherwise
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient.strip(),
            "type": "text",
            "text": {"preview_url": False, "body": message}
        }
        
        return self._make_request(payload)
    
    def send_typing_indicator(self, message_id: str) -> Optional[requests.Response]:
        """
        Send typing indicator for a message.
        
        Args:
            message_id: WhatsApp message ID
            
        Returns:
            Response object if successful, None otherwise
        """
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
            "typing_indicator": {"type": "text"}
        }
        
        return self._make_request(payload)
    
    def _make_request(self, payload: Dict[str, Any]) -> Optional[requests.Response]:
        """
        Make a POST request to WhatsApp API.
        
        Args:
            payload: Request payload
            
        Returns:
            Response object if successful, None otherwise
        """
        try:
            url = self._get_base_url()
            headers = self._get_headers()
            
            # Reduced timeout for faster failure detection
            response = self._session.post(
                url,
                json=payload,  # Use json instead of data for better performance
                headers=headers,
                timeout=8  # Reduced from 10 for faster response
            )
            
            if response.status_code >= 400:
                self._log_error(response)
                return response  # Return response for error handling
            
            return response
            
        except requests.Timeout:
            self._logger.error("Request timeout")
            return None
        except requests.RequestException as e:
            self._logger.error(f"Request failed: {e}")
            return None
        except Exception as e:
            self._logger.error(f"Unexpected error: {e}", exc_info=True)
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
            self._logger.debug(f"Response body: {response.text}")
        except:
            self._logger.error(f"HTTP {response.status_code} error: {response.text}")

