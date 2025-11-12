"""Service container for dependency injection (IoC Container Pattern)."""
import logging
from typing import Optional
import os

from app.domain.interfaces.message_provider import IMessageProvider
from app.domain.interfaces.ai_provider import IAIProvider
from app.domain.interfaces.thread_repository import IThreadRepository
from app.domain.interfaces.vertical_manager import IVerticalManager
from app.application.use_cases.process_message_use_case import ProcessMessageUseCase
from app.infrastructure.factories.provider_factory import ProviderFactory
from app.infrastructure.managers.vertical_manager import VerticalManager
from app.infrastructure.factories.flights_factory import FlightsVerticalFactory


class ServiceContainer:
    """
    Service container implementing Dependency Injection pattern.
    
    Follows Singleton pattern and Dependency Inversion Principle.
    Uses Factory Pattern to create providers based on configuration.
    """
    
    _instance: Optional['ServiceContainer'] = None
    _thread_repository: Optional[IThreadRepository] = None
    _message_provider: Optional[IMessageProvider] = None
    _vertical_manager: Optional[IVerticalManager] = None
    _ai_provider: Optional[IAIProvider] = None
    _process_message_use_case: Optional[ProcessMessageUseCase] = None
    _verticals_initialized: bool = False
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize service container."""
        self._logger = logging.getLogger(__name__)
    
    def get_thread_repository(self) -> IThreadRepository:
        """Get or create thread repository instance."""
        if self._thread_repository is None:
            storage_type = os.getenv("THREAD_STORAGE_TYPE", "redis")
            try:
                self._thread_repository = ProviderFactory.create_thread_repository(storage_type)
                self._logger.info(f"ThreadRepository created with {storage_type}")
            except Exception as e:
                self._logger.error(f"Failed to create ThreadRepository: {e}")
                raise
        return self._thread_repository
    
    def get_message_provider(self) -> IMessageProvider:
        """Get or create message provider instance."""
        if self._message_provider is None:
            provider_type = os.getenv("MESSAGE_PROVIDER", "whatsapp")
            try:
                self._message_provider = ProviderFactory.create_message_provider(provider_type)
                self._logger.info(f"MessageProvider created: {provider_type}")
            except Exception as e:
                self._logger.error(f"Failed to create MessageProvider: {e}")
                raise
        return self._message_provider
    
    def get_vertical_manager(self) -> IVerticalManager:
        """Get or create vertical manager instance."""
        if self._vertical_manager is None:
            try:
                self._vertical_manager = VerticalManager()
                self._logger.info("VerticalManager created")
                
                # Initialize verticals
                self._initialize_verticals()
            except Exception as e:
                self._logger.error(f"Failed to create VerticalManager: {e}")
                raise
        return self._vertical_manager
    
    def _initialize_verticals(self) -> None:
        """Initialize all travel verticals."""
        if self._verticals_initialized:
            return
        
        try:
            # Initialize flights vertical
            FlightsVerticalFactory.initialize_vertical(self._vertical_manager)
            
            # Future: Add other verticals here
            # HotelsVerticalFactory.initialize_vertical(self._vertical_manager)
            # TransfersVerticalFactory.initialize_vertical(self._vertical_manager)
            
            self._verticals_initialized = True
            self._logger.info("All verticals initialized")
        except Exception as e:
            self._logger.error(f"Failed to initialize verticals: {e}")
            raise
    
    def get_ai_provider(self) -> IAIProvider:
        """Get or create AI provider instance."""
        if self._ai_provider is None:
            provider_type = os.getenv("AI_PROVIDER", "openai")
            thread_repository = self.get_thread_repository()
            vertical_manager = self.get_vertical_manager()
            try:
                self._ai_provider = ProviderFactory.create_ai_provider(
                    provider_type=provider_type,
                    thread_repository=thread_repository,
                    vertical_manager=vertical_manager
                )
                self._logger.info(f"AIProvider created: {provider_type}")
            except Exception as e:
                self._logger.error(f"Failed to create AIProvider: {e}")
                raise
        return self._ai_provider
    
    def get_process_message_use_case(self) -> ProcessMessageUseCase:
        """Get or create process message use case instance."""
        if self._process_message_use_case is None:
            message_provider = self.get_message_provider()
            ai_provider = self.get_ai_provider()
            self._process_message_use_case = ProcessMessageUseCase(
                message_provider=message_provider,
                ai_provider=ai_provider
            )
            self._logger.info("ProcessMessageUseCase created")
        return self._process_message_use_case
    
    # Backward compatibility methods
    def get_message_handler(self):
        """Get message handler (backward compatibility)."""
        from app.services.message_handler import MessageHandler
        use_case = self.get_process_message_use_case()
        return MessageHandler(use_case)
    
    @classmethod
    def reset(cls) -> None:
        """Reset all service instances (useful for testing)."""
        cls._instance = None
        cls._thread_repository = None
        cls._message_provider = None
        cls._vertical_manager = None
        cls._ai_provider = None
        cls._process_message_use_case = None
        cls._verticals_initialized = False

