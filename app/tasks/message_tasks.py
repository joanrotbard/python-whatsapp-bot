"""Celery tasks for processing WhatsApp messages asynchronously."""
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
        logger.debug(f"Task {task_id} completed successfully")


@celery_app.task(
    bind=True,
    base=CallbackTask,
    max_retries=3,
    default_retry_delay=60,
    name="whatsapp_bot.process_message"
)
def process_message_task(self, webhook_body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process WhatsApp message asynchronously.
    
    This task runs in background, allowing webhook to return immediately.
    
    Args:
        self: Task instance (bound task)
        webhook_body: WhatsApp webhook payload
        
    Returns:
        Processing result dictionary
    """
    try:
        logger.info("Starting Celery task to process message...")
        
        # Extract wa_id for logging
        try:
            wa_id = webhook_body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
            logger.info(f"Processing message for {wa_id}")
        except (KeyError, IndexError) as e:
            wa_id = "unknown"
            logger.warning(f"Could not extract wa_id from webhook: {e}")
        
        # Get service container (dependency injection)
        logger.debug("Getting service container...")
        container = ServiceContainer()
        logger.debug("Getting message handler...")
        message_handler = container.get_message_handler()
        logger.debug("Message handler obtained, processing...")
        
        # Process message
        message_handler.process_incoming_message(webhook_body)
        
        # Track success
        track_message_processing(wa_id, True)
        logger.info(f"✓ Message processed successfully for {wa_id}")
        
        return {"status": "success", "message": "Message processed successfully"}
        
    except Exception as exc:
        logger.error(f"✗ Error processing message in Celery task: {exc}", exc_info=True)
        
        # Track failure
        try:
            wa_id = webhook_body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
        except (KeyError, IndexError):
            wa_id = "unknown"
        track_message_processing(wa_id, False)
        
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

