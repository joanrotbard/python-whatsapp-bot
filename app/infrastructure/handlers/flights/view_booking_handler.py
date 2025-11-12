"""Handler for view_booking function."""
import logging
from typing import Dict, Any, Optional

from app.domain.interfaces.function_handler import IFunctionHandler
from app.domain.interfaces.travel_api_client import ITravelAPIClient


logger = logging.getLogger(__name__)


class ViewBookingHandler(IFunctionHandler):
    """
    Handler for view_booking function call.
    
    Retrieves and displays booking details.
    """
    
    def __init__(self, api_client: ITravelAPIClient):
        """
        Initialize view booking handler.
        
        Args:
            api_client: Travel API client for booking retrieval
        """
        self.api_client = api_client
        self._logger = logging.getLogger(__name__)
    
    def get_function_name(self) -> str:
        """Get the name of the function this handler processes."""
        return "view_booking"
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """
        Validate function parameters before execution.
        
        Args:
            parameters: Function parameters to validate
            
        Returns:
            True if parameters are valid, False otherwise
        """
        if "booking_id" not in parameters:
            self._logger.warning("Missing required parameter: booking_id")
            return False
        
        if not parameters["booking_id"]:
            self._logger.warning("booking_id cannot be empty")
            return False
        
        return True
    
    def handle(
        self,
        parameters: Dict[str, Any],
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle view_booking function call.
        
        Args:
            parameters: Function parameters from AI assistant
            user_id: Unique user identifier
            context: Optional context (e.g., conversation history)
            
        Returns:
            Result dictionary with booking details
            
        Raises:
            ValueError: If parameters are invalid
            Exception: If API call fails
        """
        if not self.validate_parameters(parameters):
            raise ValueError("Invalid parameters for view_booking")
        
        booking_id = parameters["booking_id"]
        
        self._logger.info(f"Viewing booking {booking_id} for user {user_id}")
        
        try:
            booking = self.api_client.get_booking(booking_id, user_id=user_id)
            
            if booking is None:
                return {
                    "success": False,
                    "error": f"Booking {booking_id} not found or does not belong to user",
                    "booking": None
                }
            
            # Format response for AI assistant
            result = {
                "success": True,
                "booking": {
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
            }
            
            self._logger.info(f"Successfully retrieved booking {booking_id}")
            return result
            
        except Exception as e:
            self._logger.error(f"Error viewing booking: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to retrieve booking: {str(e)}",
                "booking": None
            }

