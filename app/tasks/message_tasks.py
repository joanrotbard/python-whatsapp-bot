"""Celery tasks for processing messages asynchronously."""
import logging
from typing import Dict, Any
from celery import Task
from app.infrastructure.celery_app import celery_app
from app.services.message_handler import MessageHandler
from app.infrastructure.service_container import ServiceContainer
from app.middleware.monitoring import track_message_processing, track_openai_call


logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """Custom task class with retry logic and error handling."""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(f"Task {task_id} failed: {exc}", exc_info=einfo)
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        pass


@celery_app.task(
    bind=True,
    base=CallbackTask,
    max_retries=3,
    default_retry_delay=60,
    name="message_bot.process_message"
)
def process_message_task(self, webhook_body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process message asynchronously via configured provider.
    
    This task runs in background, allowing webhook to return immediately.
    
    Args:
        self: Task instance (bound task)
        webhook_body: Provider webhook payload
        
    Returns:
        Processing result dictionary
    """
    try:
        # Extract user_id for logging (provider-agnostic)
        user_id = "unknown"
        try:
            # Try to get user_id from parsed message
            container = ServiceContainer()
            message_provider = container.get_message_provider()
            parsed = message_provider.parse_webhook(webhook_body)
            if parsed:
                user_id = parsed.get("user_id", "unknown")
        except (KeyError, IndexError, Exception):
            # Fallback: try to extract from webhook structure
            try:
                user_id = webhook_body["entry"][0]["changes"][0]["value"].get("contacts", [{}])[0].get("wa_id") or \
                          webhook_body["entry"][0]["changes"][0]["value"].get("messages", [{}])[0].get("from", "unknown")
            except (KeyError, IndexError):
                user_id = "unknown"
        
        logger.info(f"Processing message for {user_id}")
        
        # Get service container and process message
        container = ServiceContainer()
        message_handler = container.get_message_handler()
        message_handler.process_incoming_message(webhook_body)
        
        # Track success
        track_message_processing(user_id, True)
        logger.info(f"Message processed successfully for {user_id}")
        
        return {"status": "success", "message": "Message processed successfully"}
        
    except Exception as exc:
        logger.error(f"Task failed: {exc}", exc_info=True)
        
        # Track failure
        try:
            container = ServiceContainer()
            message_provider = container.get_message_provider()
            parsed = message_provider.parse_webhook(webhook_body)
            if parsed:
                user_id = parsed.get("user_id", "unknown")
            else:
                user_id = "unknown"
        except Exception:
            user_id = "unknown"
        track_message_processing(user_id, False)
        
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

