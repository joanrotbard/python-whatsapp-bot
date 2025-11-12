"""Domain interfaces following Dependency Inversion Principle."""

from app.domain.interfaces.message_provider import IMessageProvider
from app.domain.interfaces.ai_provider import IAIProvider
from app.domain.interfaces.thread_repository import IThreadRepository
from app.domain.interfaces.conversation_repository import IConversationRepository
from app.domain.interfaces.function_handler import IFunctionHandler
from app.domain.interfaces.travel_api_client import ITravelAPIClient
from app.domain.interfaces.vertical_manager import IVerticalManager

__all__ = [
    "IMessageProvider",
    "IAIProvider",
    "IThreadRepository",
    "IConversationRepository",
    "IFunctionHandler",
    "ITravelAPIClient",
    "IVerticalManager",
]

