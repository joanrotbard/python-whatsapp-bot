"""Webhook API endpoints for receiving WhatsApp events."""
import logging
import json
from typing import Dict, Any, Tuple

from flask import Blueprint, request, jsonify, current_app

from app.decorators.security import signature_required
from app.utils.webhook_parser import WebhookParser
from app.middleware.monitoring import track_message_processing

# Try to import Celery task, but don't fail if Celery is not available
CELERY_AVAILABLE = False
process_message_task = None
celery_app = None

try:
    from app.tasks.message_tasks import process_message_task
    from app.infrastructure.celery_app import celery_app
    CELERY_AVAILABLE = True
except Exception:
    pass


webhook_blueprint = Blueprint("webhook", __name__)
_logger = logging.getLogger(__name__)


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
        
        if status_type == "failed":
            errors = status.get("errors", [])
            _logger.error(f"Message {message_id} failed: {errors}")


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
            if CELERY_AVAILABLE and celery_app:
                try:
                    # Check if Celery workers are available (with timeout)
                    try:
                        inspect = celery_app.control.inspect(timeout=2.0)
                        active_workers = inspect.active()
                        
                        if not active_workers:
                            use_async = False
                        else:
                            task = process_message_task.delay(body)
                            _logger.info(f"Message queued for async processing: task_id={task.id}, wa_id={wa_id}")
                            track_message_processing(wa_id, True)
                            use_async = True
                    except Exception:
                        use_async = False
                except Exception:
                    use_async = False
            
            # If async failed, process synchronously (like before)
            if not use_async:
                try:
                    container = current_app.config.get('service_container')
                    if not container:
                        _logger.error("Service container not available")
                        return jsonify({"status": "error", "message": "Service not available"}), 500
                    
                    message_handler = container.get_message_handler()
                    message_handler.process_incoming_message(body)
                    _logger.info(f"Message processed synchronously for {wa_id}")
                    track_message_processing(wa_id, True)
                except Exception as e:
                    _logger.error(f"Error processing message: {e}", exc_info=True)
                    track_message_processing(wa_id, False)
            
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
    
    Protected with signature verification to ensure requests come from WhatsApp.
    """
    return handle_message()

