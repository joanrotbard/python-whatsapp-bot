"""API endpoints module.

This module contains all HTTP API endpoints organized by domain.
Following event-driven architecture principles.
"""

from app.api.webhook import webhook_blueprint
from app.api.messages import messages_blueprint
from app.api.health import health_blueprint
from app.api.chat import chat_blueprint

__all__ = [
    "webhook_blueprint",
    "messages_blueprint",
    "health_blueprint",
    "chat_blueprint",
]

