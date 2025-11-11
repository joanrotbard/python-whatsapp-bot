"""Celery application factory following Factory Pattern."""
import os
import sys
import logging
from celery import Celery
from app.config.settings import Config

# Configure logging for Celery to use stdout (Railway marks stderr as errors)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,  # Explicitly send to stdout
    force=True  # Override any existing configuration
)
# Redirect stderr to stdout for Celery and its dependencies
sys.stderr = sys.stdout


def create_celery_app(app=None) -> Celery:
    """
    Create and configure Celery application.
    
    Args:
        app: Optional Flask app instance
        
    Returns:
        Configured Celery instance
    """
    celery = Celery(
        "whatsapp_bot",
        broker=Config.CELERY_BROKER_URL,
        backend=Config.CELERY_RESULT_BACKEND,
        include=["app.tasks.message_tasks"]
    )
    
    # Celery configuration
    celery.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=300,  # 5 minutes
        task_soft_time_limit=240,  # 4 minutes
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=1000,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        
        # Ignore task results - we don't need to store them
        # This prevents Celery from trying to save results to Redis backend
        # and avoids connection issues with the result backend
        task_ignore_result=True,
        
        # Worker logging configuration - ensure logs go to stdout
        worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
        worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
        worker_hijack_root_logger=False,  # Don't hijack root logger
    )
    
    # Update config from Flask app if provided
    if app:
        celery.conf.update(app.config)
    
    return celery


# Create default Celery instance
celery_app = create_celery_app()

