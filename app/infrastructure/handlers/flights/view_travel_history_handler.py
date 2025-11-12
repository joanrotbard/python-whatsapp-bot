"""Handler for view_travel_history function."""
import logging
from typing import Dict, Any, Optional

from app.domain.interfaces.function_handler import IFunctionHandler
from app.domain.interfaces.travel_api_client import ITravelAPIClient


logger = logging.getLogger(__name__)


class ViewTravelHistoryHandler(IFunctionHandler):
    """
    Handler for view_travel_history function call.
    
    Retrieves and displays user's travel history.
    """
    
    def __init__(self, api_client: ITravelAPIClient):
        """
        Initialize view travel history handler.
        
        Args:
            api_client: Travel API client for travel history retrieval
        """
        self.api_client = api_client
        self._logger = logging.getLogger(__name__)
    
    def get_function_name(self) -> str:
        """Get the name of the function this handler processes."""
        return "view_travel_history"
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """
        Validate function parameters before execution.
        
        Args:
            parameters: Function parameters to validate
            
        Returns:
            True if parameters are valid, False otherwise
        """
        # user_id is required but may come from context
        # If provided in parameters, validate it
        if "user_id" in parameters:
            if not parameters["user_id"]:
                self._logger.warning("user_id cannot be empty")
                return False
        
        return True
    
    def handle(
        self,
        parameters: Dict[str, Any],
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle view_travel_history function call.
        
        Args:
            parameters: Function parameters from AI assistant
            user_id: Unique user identifier (from message context)
            context: Optional context (e.g., conversation history)
            
        Returns:
            Result dictionary with travel history
            
        Raises:
            ValueError: If parameters are invalid
            Exception: If API call fails
        """
        # Use user_id from parameters if provided, otherwise use from context
        target_user_id = parameters.get("user_id", user_id)
        
        if not target_user_id:
            raise ValueError("user_id is required for view_travel_history")
        
        self._logger.info(f"Viewing travel history for user {target_user_id}")
        
        try:
            travel_history = self.api_client.get_travel_history(target_user_id)
            
            # Format response for AI assistant
            result = {
                "success": True,
                "user_id": travel_history.user_id,
                "total_bookings": len(travel_history.bookings),
                "bookings": []
            }
            
            for booking in travel_history.bookings:
                booking_data = {
                    "booking_id": booking.booking_id,
                    "flight_id": booking.flight_id,
                    "origin": booking.origin,
                    "destination": booking.destination,
                    "departure_time": booking.departure_time.isoformat(),
                    "arrival_time": booking.arrival_time.isoformat(),
                    "passengers": booking.passengers,
                    "total_price": booking.total_price,
                    "currency": booking.currency,
                    "status": booking.status,
                    "booking_date": booking.booking_date.isoformat() if booking.booking_date else None,
                    "airline": booking.airline,
                    "flight_number": booking.flight_number
                }
                result["bookings"].append(booking_data)
            
            self._logger.info(
                f"Successfully retrieved {len(travel_history.bookings)} "
                f"bookings for user {target_user_id}"
            )
            return result
            
        except Exception as e:
            self._logger.error(f"Error viewing travel history: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to retrieve travel history: {str(e)}",
                "user_id": target_user_id,
                "total_bookings": 0,
                "bookings": []
            }

