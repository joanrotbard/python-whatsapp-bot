"""Interface for external travel API clients (Adapter Pattern).

This allows switching between different travel API providers
or mocking for testing/development.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime

from app.domain.entities.flight import Flight, Booking, TravelHistory


class ITravelAPIClient(ABC):
    """
    Interface for external travel API clients following Adapter Pattern.
    
    Implementations can be swapped without changing business logic.
    Supports multiple verticals (flights, hotels, etc.).
    """
    
    @abstractmethod
    def search_flights(
        self,
        origin: str,
        destination: str,
        date: str,
        passengers: int = 1,
        **kwargs
    ) -> List[Flight]:
        """
        Search for flight options.
        
        Args:
            origin: Origin airport/city code
            destination: Destination airport/city code
            date: Travel date (ISO format or YYYY-MM-DD)
            passengers: Number of passengers
            **kwargs: Additional search parameters
            
        Returns:
            List of available flight options
            
        Raises:
            Exception: If API call fails
        """
        pass
    
    @abstractmethod
    def get_booking(self, booking_id: str, user_id: Optional[str] = None) -> Optional[Booking]:
        """
        Retrieve booking details.
        
        Args:
            booking_id: Unique booking identifier
            user_id: Optional user ID for validation
            
        Returns:
            Booking details if found, None otherwise
            
        Raises:
            Exception: If API call fails
        """
        pass
    
    @abstractmethod
    def cancel_booking(self, booking_id: str, user_id: str, confirmation: bool = False) -> bool:
        """
        Cancel a booking.
        
        Args:
            booking_id: Unique booking identifier
            user_id: User ID for authorization
            confirmation: Whether cancellation is confirmed
            
        Returns:
            True if cancellation successful, False otherwise
            
        Raises:
            ValueError: If confirmation is False
            Exception: If API call fails
        """
        pass
    
    @abstractmethod
    def get_travel_history(self, user_id: str) -> TravelHistory:
        """
        Get user's travel history (past and upcoming trips).
        
        Args:
            user_id: Unique user identifier
            
        Returns:
            User's travel history with all bookings
            
        Raises:
            Exception: If API call fails
        """
        pass

