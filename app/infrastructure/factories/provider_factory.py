"""Factory for creating provider instances (Factory Pattern)."""
import logging
from typing import Optional

from app.domain.interfaces.message_provider import IMessageProvider
from app.domain.interfaces.ai_provider import IAIProvider
from app.domain.interfaces.thread_repository import IThreadRepository

from app.infrastructure.providers.whatsapp_provider import WhatsAppProvider
from app.infrastructure.providers.openai_provider import OpenAIProvider
from app.repositories.thread_repository import RedisThreadRepository
from app.infrastructure.redis_client import RedisClientFactory


logger = logging.getLogger(__name__)


class ProviderFactory:
    """
    Factory for creating provider instances following Factory Pattern.
    
    Centralizes provider creation logic and allows easy switching between implementations.
    """
    
    @staticmethod
    def create_message_provider(provider_type: str = "whatsapp") -> IMessageProvider:
        """
        Create a message provider instance.
        
        Args:
            provider_type: Type of provider ("whatsapp", "telegram", etc.)
            
        Returns:
            IMessageProvider instance
            
        Raises:
            ValueError: If provider type is not supported
        """
        provider_type = provider_type.lower()
        
        if provider_type == "whatsapp":
            return WhatsAppProvider()
        # Future: Add more providers
        # elif provider_type == "telegram":
        #     return TelegramProvider()
        # elif provider_type == "sms":
        #     return SMSProvider()
        else:
            raise ValueError(f"Unsupported message provider type: {provider_type}")
    
    @staticmethod
    def create_ai_provider(provider_type: str = "openai", thread_repository: Optional[IThreadRepository] = None) -> IAIProvider:
        """
        Create an AI provider instance.
        
        Args:
            provider_type: Type of provider ("openai", "anthropic", etc.)
            thread_repository: Optional thread repository (will create if not provided)
            
        Returns:
            IAIProvider instance
            
        Raises:
            ValueError: If provider type is not supported
        """
        provider_type = provider_type.lower()
        
        # Create thread repository if not provided
        if thread_repository is None:
            redis_client = RedisClientFactory.get_client()
            thread_repository = RedisThreadRepository(redis_client=redis_client)
        
        if provider_type == "openai":
            return OpenAIProvider(thread_repository=thread_repository)
        # Future: Add more providers
        # elif provider_type == "anthropic":
        #     return AnthropicProvider(thread_repository=thread_repository)
        # elif provider_type == "gemini":
        #     return GeminiProvider(thread_repository=thread_repository)
        else:
            raise ValueError(f"Unsupported AI provider type: {provider_type}")
    
    @staticmethod
    def create_thread_repository(storage_type: str = "redis") -> IThreadRepository:
        """
        Create a thread repository instance.
        
        Args:
            storage_type: Type of storage ("redis", "postgresql", etc.)
            
        Returns:
            IThreadRepository instance
            
        Raises:
            ValueError: If storage type is not supported
        """
        storage_type = storage_type.lower()
        
        if storage_type == "redis":
            redis_client = RedisClientFactory.get_client()
            return RedisThreadRepository(redis_client=redis_client)
        # Future: Add more storage backends
        # elif storage_type == "postgresql":
        #     return PostgreSQLThreadRepository()
        # elif storage_type == "mongodb":
        #     return MongoDBThreadRepository()
        else:
            raise ValueError(f"Unsupported storage type: {storage_type}")

