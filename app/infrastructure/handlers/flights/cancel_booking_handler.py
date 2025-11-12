"""Handler for cancel_booking function."""
import logging
from typing import Dict, Any, Optional

from app.domain.interfaces.function_handler import IFunctionHandler
from app.domain.interfaces.travel_api_client import ITravelAPIClient


logger = logging.getLogger(__name__)


class CancelBookingHandler(IFunctionHandler):
    """
    Handler for cancel_booking function call.
    
    Cancels a booking after confirmation.
    """
    
    def __init__(self, api_client: ITravelAPIClient):
        """
        Initialize cancel booking handler.
        
        Args:
            api_client: Travel API client for booking cancellation
        """
        self.api_client = api_client
        self._logger = logging.getLogger(__name__)
    
    def get_function_name(self) -> str:
        """Get the name of the function this handler processes."""
        return "cancel_booking"
    
    def get_function_schema(self) -> Dict[str, Any]:
        """
        Get OpenAI function schema for cancel_booking.
        
        Returns:
            OpenAI function schema dictionary
        """
        return {
            "type": "function",
            "function": {
                "name": "cancel_booking",
                "description": "Cancel a booking if the traveler confirms. Always confirm with the user before canceling.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "booking_id": {
                            "type": "string",
                            "description": "Booking identifier to cancel (e.g., BK12345678)"
                        },
                        "confirmation": {
                            "type": "boolean",
                            "description": "Whether the user has confirmed they want to cancel this booking. Must be true to proceed with cancellation."
                        }
                    },
                    "required": ["booking_id", "confirmation"]
                }
            }
        }
    
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
        
        if "confirmation" not in parameters:
            self._logger.warning("Missing required parameter: confirmation")
            return False
        
        if not parameters["booking_id"]:
            self._logger.warning("booking_id cannot be empty")
            return False
        
        # Validate confirmation is boolean
        confirmation = parameters["confirmation"]
        if not isinstance(confirmation, bool):
            # Try to convert string to boolean
            if isinstance(confirmation, str):
                confirmation_lower = confirmation.lower()
                if confirmation_lower not in ["true", "false", "yes", "no", "1", "0"]:
                    self._logger.warning(f"Invalid confirmation value: {confirmation}")
                    return False
            else:
                self._logger.warning(f"confirmation must be a boolean, got: {type(confirmation)}")
                return False
        
        return True
    
    def handle(
        self,
        parameters: Dict[str, Any],
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle cancel_booking function call.
        
        Args:
            parameters: Function parameters from AI assistant
            user_id: Unique user identifier
            context: Optional context (e.g., conversation history)
            
        Returns:
            Result dictionary with cancellation status
            
        Raises:
            ValueError: If parameters are invalid or confirmation is False
            Exception: If API call fails
        """
        if not self.validate_parameters(parameters):
            raise ValueError("Invalid parameters for cancel_booking")
        
        booking_id = parameters["booking_id"]
        confirmation = parameters["confirmation"]
        
        # Convert string confirmation to boolean if needed
        if isinstance(confirmation, str):
            confirmation_lower = confirmation.lower()
            confirmation = confirmation_lower in ["true", "yes", "1"]
        
        if not confirmation:
            return {
                "success": False,
                "cancelled": False,
                "error": "Cancellation requires user confirmation",
                "message": "Please confirm that you want to cancel this booking."
            }
        
        self._logger.info(f"Cancelling booking {booking_id} for user {user_id}")
        
        try:
            success = self.api_client.cancel_booking(
                booking_id=booking_id,
                user_id=user_id,
                confirmation=True
            )
            
            if success:
                result = {
                    "success": True,
                    "cancelled": True,
                    "booking_id": booking_id,
                    "message": f"Booking {booking_id} has been successfully cancelled."
                }
                self._logger.info(f"Successfully cancelled booking {booking_id}")
            else:
                result = {
                    "success": False,
                    "cancelled": False,
                    "booking_id": booking_id,
                    "error": "Failed to cancel booking. Booking may not exist or may already be cancelled."
                }
                self._logger.warning(f"Failed to cancel booking {booking_id}")
            
            return result
            
        except ValueError as e:
            # Handle validation errors
            self._logger.warning(f"Validation error cancelling booking: {e}")
            return {
                "success": False,
                "cancelled": False,
                "error": str(e)
            }
        except Exception as e:
            self._logger.error(f"Error cancelling booking: {e}", exc_info=True)
            return {
                "success": False,
                "cancelled": False,
                "error": f"Failed to cancel booking: {str(e)}"
            }

