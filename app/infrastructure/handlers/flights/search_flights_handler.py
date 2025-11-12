"""Handler for search_flights function."""
import logging
from typing import Dict, Any, Optional

from app.domain.interfaces.function_handler import IFunctionHandler
from app.domain.interfaces.travel_api_client import ITravelAPIClient


logger = logging.getLogger(__name__)


class SearchFlightsHandler(IFunctionHandler):
    """
    Handler for search_flights function call.
    
    Searches for flight options based on user preferences.
    """
    
    def __init__(self, api_client: ITravelAPIClient):
        """
        Initialize search flights handler.
        
        Args:
            api_client: Travel API client for flight searches
        """
        self.api_client = api_client
        self._logger = logging.getLogger(__name__)
    
    def get_function_name(self) -> str:
        """Get the name of the function this handler processes."""
        return "search_flights"
    
    def get_function_schema(self) -> Dict[str, Any]:
        """
        Get OpenAI function schema for search_flights.
        
        Returns:
            OpenAI function schema dictionary
        """
        return {
            "type": "function",
            "function": {
                "name": "search_flights",
                "description": "Find and suggest flight options based on user preferences (origin, destination, travel dates, number of passengers, etc.)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "origin": {
                            "type": "string",
                            "description": "Origin airport or city code (e.g., JFK, LAX, New York, NYC)"
                        },
                        "destination": {
                            "type": "string",
                            "description": "Destination airport or city code (e.g., LHR, CDG, Paris, London)"
                        },
                        "date": {
                            "type": "string",
                            "description": "Travel date in YYYY-MM-DD format (e.g., 2024-06-15)"
                        },
                        "passengers": {
                            "type": "integer",
                            "description": "Number of passengers",
                            "default": 1,
                            "minimum": 1
                        }
                    },
                    "required": ["origin", "destination", "date"]
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
        required = ["origin", "destination", "date"]
        
        for param in required:
            if param not in parameters:
                self._logger.warning(f"Missing required parameter: {param}")
                return False
        
        # Validate passengers if provided
        if "passengers" in parameters:
            try:
                passengers = int(parameters["passengers"])
                if passengers <= 0:
                    self._logger.warning("passengers must be positive")
                    return False
            except (ValueError, TypeError):
                self._logger.warning("passengers must be an integer")
                return False
        
        return True
    
    def handle(
        self,
        parameters: Dict[str, Any],
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle search_flights function call.
        
        Args:
            parameters: Function parameters from AI assistant
            user_id: Unique user identifier
            context: Optional context (e.g., conversation history)
            
        Returns:
            Result dictionary with flight options
            
        Raises:
            ValueError: If parameters are invalid
            Exception: If API call fails
        """
        if not self.validate_parameters(parameters):
            raise ValueError("Invalid parameters for search_flights")
        
        origin = parameters["origin"]
        destination = parameters["destination"]
        date = parameters["date"]
        passengers = int(parameters.get("passengers", 1))
        
        self._logger.info(
            f"Searching flights: {origin} -> {destination} on {date} "
            f"for {passengers} passenger(s) (user: {user_id})"
        )
        
        try:
            flights = self.api_client.search_flights(
                origin=origin,
                destination=destination,
                date=date,
                passengers=passengers
            )
            
            # Format response for AI assistant
            result = {
                "success": True,
                "count": len(flights),
                "flights": []
            }
            
            for flight in flights:
                flight_data = {
                    "flight_id": flight.flight_id,
                    "origin": flight.origin,
                    "destination": flight.destination,
                    "departure_time": flight.departure_time.isoformat(),
                    "arrival_time": flight.arrival_time.isoformat(),
                    "airline": flight.airline,
                    "flight_number": flight.flight_number,
                    "price": flight.price,
                    "currency": flight.currency,
                    "available_seats": flight.available_seats,
                    "duration_minutes": flight.duration_minutes
                }
                result["flights"].append(flight_data)
            
            self._logger.info(f"Found {len(flights)} flight options")
            return result
            
        except Exception as e:
            self._logger.error(f"Error searching flights: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to search flights: {str(e)}",
                "count": 0,
                "flights": []
            }

