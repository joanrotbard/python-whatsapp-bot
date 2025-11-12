"""Messages API endpoints for sending messages via configured provider."""
import logging
import json
from typing import Dict, Tuple

from flask import Blueprint, request, jsonify, current_app

from app.decorators.security import signature_required
from app.utils.phone_validator import PhoneNumberValidator


messages_blueprint = Blueprint("messages", __name__)
_logger = logging.getLogger(__name__)


@messages_blueprint.route("/api/send-message", methods=["POST"])
@signature_required
def send_message():
    """
    API endpoint to send messages programmatically via configured provider.
    
    Protected with signature verification for security.
    
    Expected payload:
    {
        "to": "1234567890",  # Recipient identifier (phone number, user ID, etc.)
        "message": "Your message text here"
    }
    
    Returns:
        JSON response with status and message details
    """
    try:
        body = request.get_json()
        
        if not body:
            return jsonify({"status": "error", "message": "Request body required"}), 400
        
        to_number = body.get("to")
        message_text = body.get("message")
        
        if not to_number:
            return jsonify({"status": "error", "message": "Missing 'to' field"}), 400
        
        if not message_text:
            return jsonify({"status": "error", "message": "Missing 'message' field"}), 400
        
        # Validate and normalize phone number
        try:
            cleaned_digits, api_format = PhoneNumberValidator.normalize(to_number)
        except ValueError as e:
            return jsonify({"status": "error", "message": str(e)}), 400
        
        _logger.info(f"API request: to={to_number}, normalized={api_format}")
        
        # Get message provider from service container (configured via MESSAGE_PROVIDER env var)
        container = current_app.config.get('service_container')
        if not container:
            _logger.warning("Service container not in app.config, creating new instance")
            # Fallback: create container on demand
            from app.infrastructure.service_container import ServiceContainer
            container = ServiceContainer()
            current_app.config['service_container'] = container
        
        try:
            message_provider = container.get_message_provider()
        except Exception as e:
            _logger.error(f"Failed to get message provider: {e}", exc_info=True)
            return jsonify({"status": "error", "message": f"Service initialization error: {str(e)}"}), 500
        
        # Send message using provider interface
        result = message_provider.send_text_message(api_format, message_text)
        
        if result is None:
            return jsonify({
                "status": "error",
                "message": "Connection timeout or network error",
                "to": cleaned_digits
            }), 500
        
        if result.get("status") == "success":
            return _build_success_response_from_dict(result, cleaned_digits, api_format)
        else:
            return _build_error_response_from_dict(result, cleaned_digits)
            
    except json.JSONDecodeError:
        _logger.error("Invalid JSON in request")
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400
    except Exception as e:
        _logger.error(f"Error in send-message endpoint: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Internal error: {str(e)}"}), 500


def _build_success_response_from_dict(result: Dict, cleaned_digits: str, api_format: str) -> Tuple[Dict, int]:
    """Build success response from provider result dictionary."""
    response_data = result.get("response", {})
    message_id = result.get("message_id")
    
    # Provider may normalize recipient ID
    normalized_number = cleaned_digits
    if "contacts" in response_data and response_data["contacts"]:
        normalized_id = response_data["contacts"][0].get("wa_id") or response_data["contacts"][0].get("id")
        if normalized_id and normalized_id != cleaned_digits:
            normalized_number = normalized_id
            _logger.warning(
                f"Recipient normalized: {cleaned_digits} -> {normalized_number}. "
                f"Add both to allowed recipients list if required."
            )
    
    return jsonify({
        "status": "success",
        "message": "Message accepted",
        "to": cleaned_digits,
        "sent_to": api_format,
        "normalized_to": normalized_number,
        "message_id": message_id,
        "provider_response": response_data
    }), 200


def _build_error_response_from_dict(result: Dict, cleaned_digits: str) -> Tuple[Dict, int]:
    """Build error response from provider result dictionary."""
    error_message = result.get("error_message", "Unknown error")
    error_code = result.get("error_code")
    http_status = result.get("http_status", 500)

    # Special handling for common errors
    if http_status == 401:
        error_message = "Authentication failed. Check your credentials."
    elif http_status == 403:
        error_message = (
            f"Recipient {cleaned_digits} not authorized. "
            f"Add it in provider dashboard if required."
        )
    elif http_status == 400:
        error_message = f"Invalid recipient {cleaned_digits}. Check recipient format and permissions."

    _logger.error(f"Failed to send message: {error_message}")

    return jsonify({
        "status": "error",
        "message": error_message,
        "to": cleaned_digits,
        "http_status": http_status
    }), http_status

