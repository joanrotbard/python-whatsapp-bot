"""Factory for initializing flights vertical (Factory Pattern).

This factory sets up all components needed for the flights vertical:
- API client
- Function handlers
- Registration with vertical manager
"""
import logging

from app.domain.interfaces.travel_api_client import ITravelAPIClient
from app.domain.interfaces.vertical_manager import IVerticalManager
from app.infrastructure.clients.mock_travel_api_client import MockTravelAPIClient
from app.infrastructure.handlers.flights import (
    SearchFlightsHandler,
    ViewBookingHandler,
    CancelBookingHandler,
    ViewTravelHistoryHandler
)


logger = logging.getLogger(__name__)


class FlightsVerticalFactory:
    """
    Factory for initializing flights vertical components.
    
    Follows Factory Pattern to centralize vertical setup logic.
    Makes it easy to add new verticals in the future.
    """
    
    @staticmethod
    def create_api_client() -> ITravelAPIClient:
        """
        Create travel API client for flights.
        
        Currently returns mock client. In production, this would
        return a real API client implementation.
        
        Returns:
            ITravelAPIClient instance
        """
        # TODO: Replace with real API client when available
        # For now, use mock client
        return MockTravelAPIClient()
    
    @staticmethod
    def initialize_vertical(vertical_manager: IVerticalManager) -> None:
        """
        Initialize flights vertical and register all handlers.
        
        This method:
        1. Creates API client
        2. Creates all function handlers
        3. Registers handlers with vertical manager
        
        Args:
            vertical_manager: Vertical manager to register handlers with
        """
        logger.info("Initializing flights vertical...")
        
        # Create API client
        api_client = FlightsVerticalFactory.create_api_client()
        
        # Create and register handlers
        handlers = [
            SearchFlightsHandler(api_client),
            ViewBookingHandler(api_client),
            CancelBookingHandler(api_client),
            ViewTravelHistoryHandler(api_client),
        ]
        
        # Register all handlers
        for handler in handlers:
            vertical_manager.register_handler(handler, vertical="flights")
            logger.info(f"Registered handler: {handler.get_function_name()}")
        
        logger.info(f"Flights vertical initialized with {len(handlers)} handlers")

