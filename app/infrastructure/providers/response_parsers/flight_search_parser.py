"""Flight search response parser.

Parses and transforms flight search tool results into a clean format
optimized for LLM consumption.
"""
import logging
from typing import Dict, Any

from app.infrastructure.providers.response_parsers import ResponseParser
from app.infrastructure.providers.message_instructions import get_instruction_registry

logger = logging.getLogger(__name__)


class FlightSearchResponseParser(ResponseParser):
    """Parser for flight search tool results."""
    
    def can_parse(self, tool_name: str, result: Any) -> bool:
        """Check if this is a flight search result that can be parsed."""
        if tool_name != "search_flights":
            return False
        
        if not isinstance(result, dict):
            return False
        
        return (
            result.get("success") and
            result.get("data") and
            "Fares" in result.get("data", {})
        )
    
    def parse(self, tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Parse flight search response and return clean result."""
        from app.utils.flight_response_parser import parse_flight_search_response
        
        try:
            parsed_result = parse_flight_search_response(
                result["data"],
                sort_order='cheapest',
                limit=5
            )
            
            # Get message instruction for this use case
            instruction_registry = get_instruction_registry()
            instruction = instruction_registry.get_instruction("search_flights", {
                "success": result.get("success", True)
            })
            
            # Create a clean result with only parsed data (no huge raw data)
            clean_result = {
                "success": result.get("success", True),
                "message": (
                    f"{result.get('message', '')} "
                    f"Found {parsed_result['totalCount']} total flights. "
                    f"Showing top {len(parsed_result['options'])} cheapest options."
                ),
                "cost_center_used": result.get("cost_center_used"),
                "cost_center_message": result.get("cost_center_message"),
                "all_flights_context": parsed_result["allFlightsContext"],
                "total_flights_count": parsed_result["totalCount"]
            }
            
            # Add instruction if available
            if instruction:
                clean_result["formatting_instruction"] = instruction
            
            return clean_result
            
        except Exception as e:
            logger.warning(f"Failed to parse flight search response: {e}")
            raise ValueError(f"Failed to parse flight search response: {e}") from e

