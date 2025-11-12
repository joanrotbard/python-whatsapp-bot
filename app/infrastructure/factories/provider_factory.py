"""Factory for creating provider instances (Factory Pattern)."""
import logging
from typing import Optional

from app.domain.interfaces.message_provider import IMessageProvider
from app.domain.interfaces.ai_provider import IAIProvider
from app.domain.interfaces.thread_repository import IThreadRepository
from app.domain.interfaces.conversation_repository import IConversationRepository
from app.domain.interfaces.vertical_manager import IVerticalManager

from app.infrastructure.providers.whatsapp_provider import WhatsAppProvider
from app.infrastructure.providers.openai_provider import OpenAIProvider
from app.infrastructure.providers.langchain_provider import LangChainProvider
from app.infrastructure.repositories.thread_repository import RedisThreadRepository
from app.infrastructure.repositories.conversation_repository import RedisConversationRepository
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
    def create_ai_provider(
        provider_type: str = "langchain",
        conversation_repository: Optional[IConversationRepository] = None,
        vertical_manager: Optional[IVerticalManager] = None,
        thread_repository: Optional[IThreadRepository] = None  # Deprecated, kept for backward compatibility
    ) -> IAIProvider:
        """
        Create an AI provider instance.
        
        Args:
            provider_type: Type of provider ("openai", "anthropic", etc.)
            conversation_repository: Conversation repository for storing message history
            vertical_manager: Optional vertical manager for function calls
            thread_repository: Deprecated - kept for backward compatibility
            
        Returns:
            IAIProvider instance
            
        Raises:
            ValueError: If provider type is not supported
        """
        provider_type = provider_type.lower()
        
        if provider_type == "langchain":
            # LangChain provider uses built-in memory, no conversation repository needed
            if LangChainProvider is None:
                raise ImportError(
                    "LangChain dependencies are not installed. "
                    "Please install them with: pip install langchain langchain-openai langchain-core pydantic"
                )
            return LangChainProvider(
                vertical_manager=vertical_manager
            )
        elif provider_type == "openai":
            # Legacy OpenAI provider (still supported but deprecated)
            # Create conversation repository if not provided
            if conversation_repository is None:
                redis_client = RedisClientFactory.get_client()
                conversation_repository = RedisConversationRepository(redis_client=redis_client)
            
            return OpenAIProvider(
                conversation_repository=conversation_repository,
                vertical_manager=vertical_manager
            )
        # Future: Add more providers
        # elif provider_type == "anthropic":
        #     return AnthropicProvider(vertical_manager=vertical_manager)
        # elif provider_type == "gemini":
        #     return GeminiProvider(vertical_manager=vertical_manager)
        else:
            raise ValueError(f"Unsupported AI provider type: {provider_type}")
    
    @staticmethod
    def create_conversation_repository(storage_type: str = "redis") -> IConversationRepository:
        """
        Create a conversation repository instance.
        
        Args:
            storage_type: Type of storage ("redis", "postgresql", etc.)
            
        Returns:
            IConversationRepository instance
            
        Raises:
            ValueError: If storage type is not supported
        """
        storage_type = storage_type.lower()
        
        if storage_type == "redis":
            redis_client = RedisClientFactory.get_client()
            return RedisConversationRepository(redis_client=redis_client)
        # Future: Add more storage backends
        # elif storage_type == "postgresql":
        #     return PostgreSQLConversationRepository()
        # elif storage_type == "mongodb":
        #     return MongoDBConversationRepository()
        else:
            raise ValueError(f"Unsupported storage type: {storage_type}")
    
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

