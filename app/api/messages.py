"""Messages API endpoints for sending WhatsApp messages."""
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
    API endpoint to send WhatsApp messages programmatically.
    
    Protected with signature verification for security.
    
    Expected payload:
    {
        "to": "1234567890",  # Phone number with country code
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
        
        # Get WhatsApp service from service container
        container = current_app.config.get('service_container')
        if not container:
            _logger.warning("Service container not in app.config, creating new instance")
            # Fallback: create container on demand
            from app.infrastructure.service_container import ServiceContainer
            container = ServiceContainer()
            current_app.config['service_container'] = container
        
        try:
            whatsapp_service = container.get_whatsapp_service()
        except Exception as e:
            _logger.error(f"Failed to get WhatsApp service: {e}", exc_info=True)
            return jsonify({"status": "error", "message": f"Service initialization error: {str(e)}"}), 500
        
        # Send message
        response = whatsapp_service.send_text_message(api_format, message_text)
        
        if response is None:
            return jsonify({
                "status": "error",
                "message": "Connection timeout or network error",
                "to": cleaned_digits
            }), 500
        
        if response.status_code == 200:
            return _build_success_response(response, cleaned_digits, api_format)
        else:
            return _build_error_response(response, cleaned_digits)
            
    except json.JSONDecodeError:
        _logger.error("Invalid JSON in request")
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400
    except Exception as e:
        _logger.error(f"Error in send-message endpoint: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Internal error: {str(e)}"}), 500


def _build_success_response(response, cleaned_digits: str, api_format: str) -> Tuple[Dict, int]:
    """Build success response for API endpoint."""
    try:
        response_data = response.json()
    except:
        response_data = {}
    
    normalized_number = cleaned_digits
    if "contacts" in response_data and response_data["contacts"]:
        normalized_number = response_data["contacts"][0].get("wa_id", cleaned_digits)
        if normalized_number != cleaned_digits:
            _logger.warning(
                f"Number normalized: {cleaned_digits} -> {normalized_number}. "
                f"Add both to allowed recipients list."
            )
    
    message_id = None
    if "messages" in response_data and response_data["messages"]:
        message_id = response_data["messages"][0].get("id")
    
    return jsonify({
        "status": "success",
        "message": "Message accepted by WhatsApp API",
        "to": cleaned_digits,
        "sent_to": api_format,
        "normalized_to": normalized_number,
        "message_id": message_id,
        "whatsapp_response": response_data
    }), 200


def _build_error_response(response, cleaned_digits: str) -> Tuple[Dict, int]:
    """Build error response for API endpoint."""
    error_message = f"WhatsApp API error (status {response.status_code})"
    error_code = None
    
    try:
        error_data = response.json()
        if 'error' in error_data:
            error_message = error_data['error'].get('message', error_message)
            error_code = error_data['error'].get('code')
    except:
        error_message = response.text or error_message
    
    # Special handling for common errors
    if response.status_code == 401:
        error_message = "Authentication failed. Check your ACCESS_TOKEN."
    elif response.status_code == 403 and error_code in [131047, 131026]:
        error_message = (
            f"Recipient {cleaned_digits} not in allowed list. "
            f"Add it in Meta App Dashboard > WhatsApp > API Setup."
        )
    elif response.status_code == 400 and error_code in [131026, 131047]:
        error_message = f"Invalid recipient {cleaned_digits}. Add to allowed recipients list."
    
    _logger.error(f"Failed to send message: {error_message}")
    
    return jsonify({
        "status": "error",
        "message": error_message,
        "to": cleaned_digits,
        "http_status": response.status_code
    }), response.status_code

