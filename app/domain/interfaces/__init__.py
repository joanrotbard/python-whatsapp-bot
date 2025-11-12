"""Domain interfaces following Dependency Inversion Principle."""

from app.domain.interfaces.message_provider import IMessageProvider
from app.domain.interfaces.ai_provider import IAIProvider
from app.domain.interfaces.thread_repository import IThreadRepository

__all__ = [
    "IMessageProvider",
    "IAIProvider",
    "IThreadRepository",
]

