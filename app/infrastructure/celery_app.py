"""Celery application factory following Factory Pattern."""
import os
from celery import Celery
from app.config.settings import Config


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
    )
    
    # Update config from Flask app if provided
    if app:
        celery.conf.update(app.config)
    
    return celery


# Create default Celery instance
celery_app = create_celery_app()

