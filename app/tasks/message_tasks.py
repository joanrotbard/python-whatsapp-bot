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
        logger.info("=" * 80)
        logger.info("CELERY TASK STARTED - Processing WhatsApp message")
        logger.info(f"Task ID: {self.request.id}")
        logger.info("=" * 80)
        
        # Extract wa_id for logging
        try:
            wa_id = webhook_body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
            logger.info(f"Processing message for wa_id: {wa_id}")
        except (KeyError, IndexError) as e:
            wa_id = "unknown"
            logger.warning(f"Could not extract wa_id from webhook: {e}")
            logger.warning(f"Webhook body keys: {list(webhook_body.keys())}")
        
        # Get service container (dependency injection)
        logger.info("Step 1: Getting service container...")
        container = ServiceContainer()
        logger.info("✓ Service container obtained")
        
        logger.info("Step 2: Getting message handler...")
        message_handler = container.get_message_handler()
        logger.info("✓ Message handler obtained")
        
        logger.info("Step 3: Processing incoming message...")
        # Process message
        message_handler.process_incoming_message(webhook_body)
        logger.info("✓ Message processing completed")
        
        # Track success
        track_message_processing(wa_id, True)
        logger.info("=" * 80)
        logger.info(f"✓✓✓ CELERY TASK COMPLETED SUCCESSFULLY for {wa_id}")
        logger.info("=" * 80)
        
        return {"status": "success", "message": "Message processed successfully"}
        
    except Exception as exc:
        logger.error("=" * 80)
        logger.error(f"✗✗✗ CELERY TASK FAILED: {exc}")
        logger.error(f"Task ID: {self.request.id}")
        logger.error(f"Exception type: {type(exc).__name__}")
        logger.error("=" * 80, exc_info=True)
        
        # Track failure
        try:
            wa_id = webhook_body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
        except (KeyError, IndexError):
            wa_id = "unknown"
        track_message_processing(wa_id, False)
        
        # Retry with exponential backoff
        logger.warning(f"Retrying task (attempt {self.request.retries + 1}/{self.max_retries})...")
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

