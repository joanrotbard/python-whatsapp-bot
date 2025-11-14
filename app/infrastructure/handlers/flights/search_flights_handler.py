"""Handler for search_flights function."""
import json
import logging
import hashlib
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from threading import Lock

from app.domain.interfaces.function_handler import IFunctionHandler
from app.domain.interfaces.travel_api_client import ITravelAPIClient
from app.utils.flight_utils import format_date, map_cabin_class, normalize_airport_code, validate_future_date
from app.application.services.authentication_service import AuthenticationService


logger = logging.getLogger(__name__)

# Simple in-memory cache to prevent duplicate searches
# Key: (user_id, payload_hash), Value: (result, timestamp)
_search_cache: Dict[tuple, tuple] = {}
_cache_lock = Lock()
_cache_ttl = 30  # Cache for 30 seconds to prevent duplicate requests


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
                "description": "Find and suggest flight options. Requires: flight type (one-way or round-trip), origin, destination, departure date, return date (if round-trip), cabin class (defaults to economy if not specified).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "flight_type": {
                            "type": "string",
                            "enum": ["one-way", "round-trip"],
                            "description": "Type of flight: one-way or round-trip"
                        },
                        "origin": {
                            "type": "string",
                            "description": "Origin airport or city code (e.g., JFK, LAX, New York, NYC)"
                        },
                        "destination": {
                            "type": "string",
                            "description": "Destination airport or city code (e.g., LHR, CDG, Paris, London)"
                        },
                        "departure_date": {
                            "type": "string",
                            "description": "Departure date. IMPORTANT: You can pass relative date expressions directly (e.g., 'tomorrow', 'mañana', 'next monday', 'próximo martes', 'el martes que viene') OR absolute dates in YYYY-MM-DD format. The system will automatically parse relative dates. Do NOT convert relative dates to absolute dates - pass them as-is (e.g., pass 'mañana' not '2024-11-15')."
                        },
                        "return_date": {
                            "type": "string",
                            "description": "Return date. IMPORTANT: You can pass relative date expressions directly (e.g., 'tomorrow', 'mañana', 'next monday', 'próximo martes', 'el martes que viene') OR absolute dates in YYYY-MM-DD format. The system will automatically parse relative dates. Do NOT convert relative dates to absolute dates - pass them as-is. Required for round-trip, optional for one-way."
                        },
                        "cabin_class": {
                            "type": "string",
                            "enum": ["economy", "business", "first", "premium economy"],
                            "description": "Cabin class (defaults to economy if not specified)"
                        },
                        "passengers": {
                            "type": "integer",
                            "description": "Number of passengers",
                            "default": 1,
                            "minimum": 1
                        },
                        "cost_center_id": {
                            "type": "integer",
                            "description": "Cost center ID (required - user must specify which cost center to use)"
                        }
                    },
                    "required": ["flight_type", "origin", "destination", "departure_date"]
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
        required = ["flight_type", "origin", "destination", "departure_date"]
        
        for param in required:
            if param not in parameters:
                self._logger.warning(f"Missing required parameter: {param}")
                return False
        
        # Validate flight_type
        if parameters.get("flight_type") not in ["one-way", "round-trip"]:
            self._logger.warning("flight_type must be 'one-way' or 'round-trip'")
            return False
        
        # Validate return_date for round-trip
        if parameters.get("flight_type") == "round-trip" and not parameters.get("return_date"):
            self._logger.warning("return_date is required for round-trip flights")
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
    
    def _get_session_data(self) -> Optional[Dict[str, Any]]:
        """
        Get session data from authentication service.
        
        Works both in Flask app context and Celery worker context.
        """
        try:
            # Try to get from Flask app context first (if available)
            try:
                from flask import current_app
                auth_service = current_app.config.get('auth_service')
                if auth_service:
                    return auth_service.get_session()
            except RuntimeError:
                # Not in Flask app context (e.g., Celery worker)
                pass
            
            # Create new authentication service instance
            # It will use the same session storage (Redis) and get the same session
            auth_service = AuthenticationService()
            return auth_service.get_session()
        except Exception as e:
            self._logger.error(f"Failed to get session data: {e}")
            return None
    
    def _get_active_cost_centers(self, session_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get active cost centers from session data."""
        cost_centers = session_data.get("cost_centers", [])
        if not cost_centers:
            return []
        
        # Filter active cost centers - only include those explicitly marked as active
        # Do not default to active if the field is not present
        active_centers = [
            cc for cc in cost_centers 
            if isinstance(cc, dict) and cc.get("active") is True
        ]
        return active_centers
    
    def _build_payload(
        self,
        flight_type: str,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str],
        cabin_class: Optional[str],
        passengers: int,
        cost_center: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build flight availability API payload."""
        # Normalize airport codes to exactly 3 characters
        try:
            origin_code = normalize_airport_code(origin)
            destination_code = normalize_airport_code(destination)
        except ValueError as e:
            raise ValueError(f"Invalid airport code: {e}")
        
        # Validate and format dates (must be today or future, max 1 year)
        max_days_ahead = 365  # 1 year maximum
        try:
            formatted_departure = validate_future_date(departure_date, max_days_ahead=max_days_ahead)
            if not formatted_departure:
                raise ValueError(f"Invalid departure date: {departure_date}")
        except ValueError as e:
            raise ValueError(str(e))
        
        formatted_return = None
        if return_date:
            try:
                formatted_return = validate_future_date(return_date, max_days_ahead=max_days_ahead)
                if not formatted_return:
                    raise ValueError(f"Invalid return date: {return_date}")
            except ValueError as e:
                raise ValueError(str(e))
        
        # Build passengers array
        passengers_array = [{"Count": passengers, "Type": "ADT"}]
        
        # Build legs with normalized airport codes
        legs = [{
            "DepartureAirportCity": origin_code,
            "FlightDate": formatted_departure,
            "ArrivalAirportCity": destination_code
        }]
        
        # Add return leg for round-trip
        if flight_type == "round-trip" and formatted_return:
            legs.append({
                "DepartureAirportCity": destination_code,
                "FlightDate": formatted_return,
                "ArrivalAirportCity": origin_code
            })
        
        # Map cabin class
        cabin_classes = []
        if cabin_class:
            mapped_cabin = map_cabin_class(cabin_class)
            cabin_classes = [mapped_cabin]
        
        # Build feathers_passengers
        feathers_passengers = [{
            "user_id": cost_center.get("user_id"),
            "cost_center_id": cost_center.get("cost_center_id")
        }]
        
        payload = {
            "passengers": passengers_array,
            "legs": legs,
            "cabin_classes": cabin_classes,
            "feathers_passengers": feathers_passengers
        }
        
        return payload
    
    def handle(
        self,
        parameters: Dict[str, Any],
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle search_flights function call with full flow:
        1. Check cost centers
        2. Validate parameters
        3. Handle cost center selection
        4. Build payload and make API call
        
        Args:
            parameters: Function parameters from AI assistant
            user_id: Unique user identifier
            context: Optional context (e.g., conversation history)
            
        Returns:
            Result dictionary with flight options or error message
            
        Raises:
            ValueError: If parameters are invalid
            Exception: If API call fails
        """
        # Step 1: Get session data and check cost centers
        session_data = self._get_session_data()
        if not session_data:
            return {
                "success": False,
                "error": "Session not available. Please ensure you are authenticated.",
                "message": "Session not available. Please ensure you are authenticated."
            }
        
        # Step 2: Check for active cost centers
        active_cost_centers = self._get_active_cost_centers(session_data)
        
        if not active_cost_centers:
            return {
                "success": False,
                "error": "No active cost centers available",
                "message": "You don't have any active cost centers assigned. Please contact an administrator to activate a cost center."
            }
        
        # Step 3: Handle cost center selection
        cost_center = None
        
        # If only one active cost center, use it automatically
        if len(active_cost_centers) == 1:
            cc = active_cost_centers[0]
            cost_center = {
                "cost_center_id": cc.get("id"),
                "cost_center_name": cc.get("name"),
                "user_id": session_data.get("user", {}).get("id")
            }
            self._logger.info(f"Using single active cost center: {cost_center['cost_center_name']}")
        else:
            # Multiple cost centers - require user to specify
            cost_center_id = parameters.get("cost_center_id")
            if not cost_center_id:
                # User needs to choose - return list of cost centers (only show names)
                cost_centers_list = [
                    f"{i+1}. {cc.get('name', 'Unknown')}"
                    for i, cc in enumerate(active_cost_centers)
                ]
                return {
                    "success": False,
                    "error": "Cost center required",
                    "message": f"Please specify which cost center to use:\n" + "\n".join(cost_centers_list),
                    "cost_centers": active_cost_centers
                }
            
            # Find the selected cost center
            selected_cc = next(
                (cc for cc in active_cost_centers if cc.get("id") == int(cost_center_id)),
                None
            )
            if not selected_cc:
                cost_centers_list = [
                    f"{i+1}. {cc.get('name', 'Unknown')}"
                    for i, cc in enumerate(active_cost_centers)
                ]
                return {
                    "success": False,
                    "error": "Invalid cost center ID",
                    "message": f"Cost center not found or is not active. Please choose from the available cost centers:\n" + "\n".join(cost_centers_list),
                    "cost_centers": active_cost_centers
                }
            
            cost_center = {
                "cost_center_id": selected_cc.get("id"),
                "cost_center_name": selected_cc.get("name"),
                "user_id": session_data.get("user", {}).get("id")
            }
        
        # Step 4: Validate parameters
        if not self.validate_parameters(parameters):
            return {
                "success": False,
                "error": "Invalid parameters",
                "message": "Missing required flight information. Please provide: flight type, origin, destination, and departure date."
            }
        
        # Step 5: Extract parameters
        flight_type = parameters.get("flight_type", "one-way")
        origin = parameters["origin"]
        destination = parameters["destination"]
        departure_date = parameters["departure_date"]
        return_date = parameters.get("return_date")
        cabin_class = parameters.get("cabin_class")
        passengers = parameters.get("passengers")
        
        # Step 5.1: Validate required fields before searching
        # Validate passengers is present and valid
        if passengers is None:
            return {
                "success": False,
                "error": "Missing passengers",
                "message": "Number of passengers is required. Please specify how many passengers will be traveling."
            }
        
        try:
            passengers = int(passengers)
            if passengers <= 0:
                return {
                    "success": False,
                    "error": "Invalid passengers",
                    "message": "Number of passengers must be at least 1."
                }
        except (ValueError, TypeError):
            return {
                "success": False,
                "error": "Invalid passengers",
                "message": "Number of passengers must be a valid number."
            }
        
        # Validate cabin_class is present
        if not cabin_class:
            return {
                "success": False,
                "error": "Missing cabin class",
                "message": "Cabin class is required. Please specify: economy, business, first, or premium economy."
            }
        
        # Validate round-trip: airports must be different
        if flight_type == "round-trip":
            try:
                origin_code = normalize_airport_code(origin)
                destination_code = normalize_airport_code(destination)
                if origin_code == destination_code:
                    return {
                        "success": False,
                        "error": "Invalid round-trip airports",
                        "message": f"For round-trip flights, origin and destination airports must be different. "
                                   f"Both are currently: {origin_code}"
                    }
            except ValueError as e:
                return {
                    "success": False,
                    "error": "Invalid airport codes",
                    "message": f"Invalid airport code: {str(e)}"
                }
        
        # Validate dates: must be future and within 1 year
        max_days_ahead = 365  # 1 year maximum
        try:
            self._logger.debug(f"Validating departure date: '{departure_date}' (type: {type(departure_date).__name__})")
            validated_departure = validate_future_date(departure_date, max_days_ahead=max_days_ahead)
            if not validated_departure:
                self._logger.warning(f"Failed to validate departure date: '{departure_date}' - returned None")
                return {
                    "success": False,
                    "error": "Invalid departure date",
                    "message": f"Invalid departure date: {departure_date}. Date must be in the future and within 1 year. Please use a valid date format (YYYY-MM-DD) or relative expressions like 'tomorrow', 'mañana', 'next monday', etc."
                }
            self._logger.info(f"Validated departure date: '{departure_date}' -> '{validated_departure}'")
        except ValueError as e:
            self._logger.error(f"Error validating departure date '{departure_date}': {e}")
            return {
                "success": False,
                "error": "Invalid departure date",
                "message": str(e)
            }
        
        if return_date:
            try:
                validated_return = validate_future_date(return_date, max_days_ahead=max_days_ahead)
                if not validated_return:
                    return {
                        "success": False,
                        "error": "Invalid return date",
                        "message": f"Invalid return date: {return_date}. Date must be in the future and within 1 year."
                    }
                # Also validate return date is after departure date
                dep_date = datetime.strptime(validated_departure, '%Y-%m-%d').date()
                ret_date = datetime.strptime(validated_return, '%Y-%m-%d').date()
                if ret_date < dep_date:
                    return {
                        "success": False,
                        "error": "Invalid return date",
                        "message": f"Return date ({return_date}) must be after departure date ({departure_date})."
                    }
            except ValueError as e:
                return {
                    "success": False,
                    "error": "Invalid return date",
                    "message": str(e)
                }
        
        self._logger.info(
            f"Searching {flight_type} flights: {origin} -> {destination} "
            f"on {departure_date} for {passengers} passenger(s) "
            f"using cost center {cost_center['cost_center_name']}"
        )
        
        # Step 6: Build payload
        try:
            payload = self._build_payload(
                flight_type=flight_type,
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                cabin_class=cabin_class,
                passengers=passengers,
                cost_center=cost_center
            )
        except ValueError as e:
            # Handle validation errors (airport codes, dates)
            self._logger.error(f"Payload validation error: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Invalid flight search parameters: {str(e)}"
            }
        
        # Step 7: Make API call
        # Get or create authentication service (works in both Flask and Celery contexts)
        try:
            from flask import current_app
            auth_service = current_app.config.get('auth_service')
        except RuntimeError:
            # Not in Flask app context, create new instance
            auth_service = AuthenticationService()
        
        if not auth_service:
            return {
                "success": False,
                "error": "Authentication service not available",
                "message": "Authentication service not available. Please try again later."
            }
        
        session = auth_service.get_session()
        if not session:
            return {
                "success": False,
                "error": "Session not available",
                "message": "Session not available. Please ensure you are authenticated."
            }
        
        starlings_client = auth_service.api_client
        
        # Create a hash of the payload for deduplication
        payload_str = json.dumps(payload, sort_keys=True, default=str)
        payload_hash = hashlib.md5(payload_str.encode()).hexdigest()
        cache_key = (user_id, payload_hash)
        
        # Check cache for recent duplicate request
        with _cache_lock:
            current_time = time.time()
            # Clean old cache entries
            expired_keys = [
                k for k, v in _search_cache.items()
                if current_time - v[1] >= _cache_ttl
            ]
            for key in expired_keys:
                del _search_cache[key]
            
            # Check if we have a recent result for this exact search
            if cache_key in _search_cache:
                cached_result, cached_time = _search_cache[cache_key]
                age = current_time - cached_time
                self._logger.info(
                    f"Found cached flight search result (age: {age:.1f}s) - "
                    f"returning cached result to prevent duplicate API call"
                )
                return cached_result
        
        # Log search initiation with key parameters for debugging
        self._logger.info(
            f"Initiating flight availability search: {origin} -> {destination}, "
            f"date: {departure_date}, passengers: {passengers}, "
            f"cost_center: {cost_center['cost_center_name']} (hash: {payload_hash[:8]})"
        )
        
        try:
            response = starlings_client.search_flight_availability(
                payload=payload,
                access_token=session["access_token"],
                tenant=session["tenant"]
            )
            
            # Step 8: Format response
            cost_center_message = f"Using cost center: {cost_center['cost_center_name']}"
            result = {
                "success": True,
                "message": f"Found flight options for {origin} to {destination}. {cost_center_message}",
                "cost_center_used": cost_center["cost_center_name"],
                "cost_center_message": cost_center_message,
                "data": response
            }
            
            # Cache the result to prevent duplicate requests
            with _cache_lock:
                _search_cache[cache_key] = (result, time.time())
            
            self._logger.info("Flight search completed successfully")
            return result
            
        except Exception as e:
            self._logger.error(f"Error searching flights: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to search flights: {str(e)}",
                "message": f"I encountered an error while searching for flights: {str(e)}"
            }

