"""Response parsers for tool results.

This module provides a registry pattern for parsing and transforming tool results
before sending them to the LLM. This allows for extensible response processing
without modifying the main provider code.
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ResponseParser(ABC):
    """
    Abstract base class for response parsers.
    
    Each parser handles a specific tool's response format and transforms it
    into a cleaner, more LLM-friendly format.
    """
    
    @abstractmethod
    def can_parse(self, tool_name: str, result: Any) -> bool:
        """
        Check if this parser can handle the given tool result.
        
        Args:
            tool_name: Name of the tool that produced the result
            result: The result from the tool
            
        Returns:
            True if this parser can handle the result, False otherwise
        """
        pass
    
    @abstractmethod
    def parse(self, tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse and transform the tool result.
        
        Args:
            tool_name: Name of the tool that produced the result
            result: The result dictionary from the tool
            
        Returns:
            Transformed result dictionary optimized for LLM consumption
            
        Raises:
            ValueError: If the result cannot be parsed
        """
        pass


class ResponseParserRegistry:
    """
    Registry for response parsers.
    
    Uses the Registry pattern to allow extensible response parsing
    without modifying the main provider code.
    """
    
    def __init__(self):
        """Initialize the registry with default parsers."""
        self._parsers: list[ResponseParser] = []
        self._register_default_parsers()
    
    def _register_default_parsers(self):
        """Register default parsers."""
        # Import here to avoid circular dependencies
        from app.infrastructure.providers.response_parsers.flight_search_parser import (
            FlightSearchResponseParser
        )
        self.register(FlightSearchResponseParser())
    
    def register(self, parser: ResponseParser):
        """
        Register a new response parser.
        
        Args:
            parser: Parser instance to register
        """
        self._parsers.append(parser)
        logger.debug(f"Registered response parser: {parser.__class__.__name__}")
    
    def parse_result(self, tool_name: str, result: Any) -> Optional[Dict[str, Any]]:
        """
        Find and use the appropriate parser for the given tool result.
        
        Args:
            tool_name: Name of the tool that produced the result
            result: The result from the tool
            
        Returns:
            Parsed result dictionary if a parser was found and succeeded,
            None otherwise
        """
        # Ensure result is a dict if it's a JSON string
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                return None
        
        if not isinstance(result, dict):
            return None
        
        # Try each parser until one can handle it
        for parser in self._parsers:
            try:
                if parser.can_parse(tool_name, result):
                    logger.debug(f"Using parser {parser.__class__.__name__} for tool {tool_name}")
                    return parser.parse(tool_name, result)
            except Exception as e:
                logger.warning(
                    f"Parser {parser.__class__.__name__} failed for tool {tool_name}: {e}"
                )
                # Continue to next parser or return None
                continue
        
        # No parser found or all parsers failed
        return None


# Global registry instance
_parser_registry = None


def get_parser_registry() -> ResponseParserRegistry:
    """
    Get the global parser registry instance (singleton pattern).
    
    Returns:
        The global ResponseParserRegistry instance
    """
    global _parser_registry
    if _parser_registry is None:
        _parser_registry = ResponseParserRegistry()
    return _parser_registry

