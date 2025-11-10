"""Utilities for parsing WhatsApp webhook payloads."""
from typing import Dict, Any, Optional, List


class WebhookParser:
    """Utility class for parsing WhatsApp webhook payloads."""
    
    @staticmethod
    def is_status_update(webhook_body: Dict[str, Any]) -> bool:
        """
        Check if webhook is a status update.
        
        Args:
            webhook_body: Webhook payload
            
        Returns:
            True if status update, False otherwise
        """
        try:
            return bool(
                webhook_body.get("entry", [{}])[0]
                .get("changes", [{}])[0]
                .get("value", {})
                .get("statuses")
            )
        except (IndexError, KeyError, AttributeError):
            return False
    
    @staticmethod
    def is_valid_message(webhook_body: Dict[str, Any]) -> bool:
        """
        Check if webhook contains a valid message.
        
        Args:
            webhook_body: Webhook payload
            
        Returns:
            True if valid message, False otherwise
        """
        try:
            return bool(
                webhook_body.get("object")
                and webhook_body.get("entry")
                and webhook_body["entry"][0].get("changes")
                and webhook_body["entry"][0]["changes"][0].get("value")
                and webhook_body["entry"][0]["changes"][0]["value"].get("messages")
                and webhook_body["entry"][0]["changes"][0]["value"]["messages"][0]
            )
        except (IndexError, KeyError, AttributeError):
            return False
    
    @staticmethod
    def extract_statuses(webhook_body: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract status updates from webhook.
        
        Args:
            webhook_body: Webhook payload
            
        Returns:
            List of status dictionaries
        """
        try:
            return webhook_body["entry"][0]["changes"][0]["value"].get("statuses", [])
        except (IndexError, KeyError, AttributeError):
            return []

