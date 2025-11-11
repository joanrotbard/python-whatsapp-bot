"""Celery worker entry point.

This script ensures all Celery logs go to stdout so Railway doesn't mark them as errors.
"""
import sys
import logging

# Configure logging BEFORE importing Celery to ensure all logs go to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,  # Explicitly send to stdout
    force=True  # Override any existing configuration
)

# Redirect stderr to stdout for Celery and its dependencies
# This prevents Railway from marking normal logs as errors
sys.stderr = sys.stdout

# Now import Celery (it will use the logging configuration above)
from app.infrastructure.celery_app import celery_app

if __name__ == "__main__":
    celery_app.start()

