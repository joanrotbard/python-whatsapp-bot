"""Service container for dependency injection (IoC Container Pattern)."""
import logging
from typing import Optional

from app.infrastructure.redis_client import RedisClientFactory
from app.repositories.thread_repository import ThreadRepository
from app.services.whatsapp_service import WhatsAppService
from app.services.openai_service import OpenAIService
from app.services.message_handler import MessageHandler
from app.config.settings import Config


class ServiceContainer:
    """
    Service container implementing Dependency Injection pattern.
    
    Follows Singleton pattern for service instances and
    Dependency Inversion Principle.
    """
    
    _instance: Optional['ServiceContainer'] = None
    _thread_repository: Optional[ThreadRepository] = None
    _whatsapp_service: Optional[WhatsAppService] = None
    _openai_service: Optional[OpenAIService] = None
    _message_handler: Optional[MessageHandler] = None
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize service container."""
        self._logger = logging.getLogger(__name__)
    
    def get_thread_repository(self) -> ThreadRepository:
        """Get or create thread repository instance."""
        if self._thread_repository is None:
            try:
                redis_client = RedisClientFactory.get_client()
                self._thread_repository = ThreadRepository(
                    redis_client=redis_client,
                    ttl=3600  # 1 hour TTL
                )
                self._logger.info("ThreadRepository created with Redis")
            except Exception as e:
                self._logger.error(f"Failed to create ThreadRepository with Redis: {e}")
                # Fallback: create repository without Redis (will fail gracefully)
                self._thread_repository = ThreadRepository(
                    redis_client=None,
                    ttl=3600
                )
                self._logger.warning("ThreadRepository created without Redis (threads will not persist)")
        return self._thread_repository
    
    def get_whatsapp_service(self) -> WhatsAppService:
        """Get or create WhatsApp service instance."""
        if self._whatsapp_service is None:
            self._whatsapp_service = WhatsAppService()
            self._logger.debug("WhatsAppService created")
        return self._whatsapp_service
    
    def get_openai_service(self) -> OpenAIService:
        """Get or create OpenAI service instance."""
        if self._openai_service is None:
            thread_repository = self.get_thread_repository()
            self._openai_service = OpenAIService(thread_repository)
            self._logger.debug("OpenAIService created")
        return self._openai_service
    
    def get_message_handler(self) -> MessageHandler:
        """Get or create message handler instance."""
        if self._message_handler is None:
            whatsapp_service = self.get_whatsapp_service()
            openai_service = self.get_openai_service()
            self._message_handler = MessageHandler(whatsapp_service, openai_service)
            self._logger.debug("MessageHandler created")
        return self._message_handler
    
    @classmethod
    def reset(cls) -> None:
        """Reset all service instances (useful for testing)."""
        cls._instance = None
        cls._thread_repository = None
        cls._whatsapp_service = None
        cls._openai_service = None
        cls._message_handler = None

