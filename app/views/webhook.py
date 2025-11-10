"""API views and webhook handlers."""
import logging
import json
from typing import Dict, Any, Tuple

from flask import Blueprint, request, jsonify, current_app
from flask_limiter import Limiter

from app.decorators.security import signature_required
from app.utils.webhook_parser import WebhookParser
from app.utils.phone_validator import PhoneNumberValidator
from app.middleware.monitoring import track_message_processing, track_webhook_request

# Try to import Celery task, but don't fail if Celery is not available
try:
    from app.tasks.message_tasks import process_message_task
    CELERY_AVAILABLE = True
except Exception:
    CELERY_AVAILABLE = False
    process_message_task = None


webhook_blueprint = Blueprint("webhook", __name__)
_logger = logging.getLogger(__name__)

if not CELERY_AVAILABLE:
    _logger.warning("Celery not available, will use synchronous processing")


def _handle_status_updates(webhook_body: Dict[str, Any]) -> None:
    """Handle WhatsApp status update webhooks."""
    statuses = WebhookParser.extract_statuses(webhook_body)
    
    for status in statuses:
        message_id = status.get("id", "unknown")
        status_type = status.get("status", "unknown")
        recipient_id = status.get("recipient_id", "unknown")
        timestamp = status.get("timestamp", "unknown")
        
        _logger.info(
            f"Status update: message_id={message_id}, status={status_type}, "
            f"recipient={recipient_id}, timestamp={timestamp}"
        )
        
        if status_type == "sent":
            _logger.info(f"✓ Message {message_id} sent to {recipient_id}")
        elif status_type == "delivered":
            _logger.info(f"✓✓ Message {message_id} delivered to {recipient_id}")
        elif status_type == "read":
            _logger.info(f"✓✓✓ Message {message_id} read by {recipient_id}")
        elif status_type == "failed":
            errors = status.get("errors", [])
            _logger.error(f"✗ Message {message_id} failed: {errors}")


def handle_message() -> Tuple[str, int]:
    """
    Handle incoming webhook events from WhatsApp API.
    
    Uses Celery for asynchronous message processing to return immediately.
    
    Returns:
        Tuple of (response, status_code)
    """
    body = request.get_json()
    
    if not body:
        return jsonify({"status": "error", "message": "Empty request body"}), 400
    
    # Log webhook type
    if body.get("entry"):
        entry = body["entry"][0] if body["entry"] else {}
        changes = entry.get("changes", [{}])[0] if entry.get("changes") else {}
        value = changes.get("value", {})
        
        if value.get("messages"):
            _logger.info("Incoming webhook: Message event")
        elif value.get("statuses"):
            _logger.info("Incoming webhook: Status update event")
    
    # Handle status updates (synchronous, fast)
    if WebhookParser.is_status_update(body):
        _handle_status_updates(body)
        return jsonify({"status": "ok"}), 200
    
    # Handle incoming messages
    try:
        if WebhookParser.is_valid_message(body):
            # Extract wa_id for metrics
            try:
                wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
            except (KeyError, IndexError):
                wa_id = "unknown"
            
            # Try async processing with Celery first, fallback to sync if unavailable
            use_async = False
            if CELERY_AVAILABLE:
                try:
                    task = process_message_task.delay(body)
                    _logger.info(f"Message queued for async processing: task_id={task.id}, wa_id={wa_id}")
                    track_message_processing(wa_id, True)
                    use_async = True
                except Exception as e:
                    # Celery not available or error - fallback to synchronous processing
                    _logger.warning(f"Celery unavailable, processing synchronously: {e}")
                    use_async = False
            
            # If async failed, process synchronously (like before)
            if not use_async:
                try:
                    _logger.info(f"Processing message synchronously for {wa_id}")
                    # Get message handler from service container
                    container = current_app.config.get('service_container')
                    if not container:
                        _logger.error("Service container not available in app.config")
                        return jsonify({"status": "error", "message": "Service not available"}), 500
                    
                    _logger.debug("Getting message handler from container...")
                    message_handler = container.get_message_handler()
                    _logger.debug("Message handler obtained, processing message...")
                    
                    message_handler.process_incoming_message(body)
                    _logger.info(f"✓ Message processed synchronously for {wa_id}")
                    track_message_processing(wa_id, True)
                except Exception as e:
                    _logger.error(f"✗ Error processing message synchronously: {e}", exc_info=True)
                    track_message_processing(wa_id, False)
                    # Still return 200 to prevent WhatsApp retries
            
            return jsonify({"status": "ok"}), 200
        else:
            _logger.warning("Received invalid WhatsApp message")
            return jsonify({"status": "error", "message": "Not a WhatsApp API event"}), 404
            
    except json.JSONDecodeError:
        _logger.error("Failed to decode JSON")
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400
    except Exception as e:
        _logger.error(f"Unexpected error: {e}", exc_info=True)
        return jsonify({"status": "ok"}), 200  # Return success to prevent retries


def verify() -> Tuple[str, int]:
    """
    Verify webhook subscription (required by WhatsApp).
    
    Returns:
        Tuple of (challenge, status_code) or (error_response, status_code)
    """
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    
    if not (mode and token):
        _logger.info("MISSING_PARAMETER")
        return jsonify({"status": "error", "message": "Missing parameters"}), 400
    
    if mode == "subscribe" and token == current_app.config["VERIFY_TOKEN"]:
        _logger.info("WEBHOOK_VERIFIED")
        return challenge, 200
    else:
        _logger.info("VERIFICATION_FAILED")
        return jsonify({"status": "error", "message": "Verification failed"}), 403


@webhook_blueprint.route("/webhook", methods=["GET"])
def webhook_get():
    """Handle webhook verification (GET request)."""
    return verify()


@webhook_blueprint.route("/webhook", methods=["POST"])
@signature_required
def webhook_post():
    """
    Handle incoming webhook events (POST request).
    
    Rate limited to prevent abuse.
    """
    return handle_message()


@webhook_blueprint.route("/api/send-message", methods=["POST"])
def api_send_message():
    """
    API endpoint to send WhatsApp messages programmatically.
    
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
