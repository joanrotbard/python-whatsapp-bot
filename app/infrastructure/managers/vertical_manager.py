"""Vertical manager implementation (Registry Pattern).

Manages different travel verticals and routes function calls
to appropriate handlers.
"""
import logging
from typing import Dict, Optional, List

from app.domain.interfaces.vertical_manager import IVerticalManager
from app.domain.interfaces.function_handler import IFunctionHandler


logger = logging.getLogger(__name__)


class VerticalManager(IVerticalManager):
    """
    Implementation of vertical manager following Registry Pattern.
    
    Manages registration and routing of function handlers
    for different travel verticals (flights, hotels, etc.).
    """
    
    def __init__(self):
        """Initialize vertical manager with empty registry."""
        self._handlers: Dict[str, IFunctionHandler] = {}
        self._vertical_handlers: Dict[str, List[IFunctionHandler]] = {}
        self._logger = logging.getLogger(__name__)
    
    def register_handler(self, handler: IFunctionHandler, vertical: str) -> None:
        """
        Register a function handler for a specific vertical.
        
        Args:
            handler: Function handler instance
            vertical: Vertical name (e.g., "flights", "hotels")
            
        Raises:
            ValueError: If handler is invalid
        """
        if not isinstance(handler, IFunctionHandler):
            raise ValueError("Handler must implement IFunctionHandler")
        
        function_name = handler.get_function_name()
        
        if not function_name:
            raise ValueError("Handler must return a valid function name")
        
        if function_name in self._handlers:
            self._logger.warning(
                f"Handler for function '{function_name}' already exists. "
                f"Overwriting with new handler from vertical '{vertical}'"
            )
        
        self._handlers[function_name] = handler
        
        # Track by vertical
        if vertical not in self._vertical_handlers:
            self._vertical_handlers[vertical] = []
        self._vertical_handlers[vertical].append(handler)
        
        self._logger.info(
            f"Registered handler for function '{function_name}' "
            f"from vertical '{vertical}'"
        )
    
    def get_handler(self, function_name: str) -> Optional[IFunctionHandler]:
        """
        Get handler for a specific function name.
        
        Args:
            function_name: Name of the function to handle
            
        Returns:
            Function handler if found, None otherwise
        """
        return self._handlers.get(function_name)
    
    def get_all_handlers(self) -> Dict[str, IFunctionHandler]:
        """
        Get all registered handlers.
        
        Returns:
            Dictionary mapping function names to handlers
        """
        return self._handlers.copy()
    
    def get_handlers_by_vertical(self, vertical: str) -> List[IFunctionHandler]:
        """
        Get all handlers for a specific vertical.
        
        Args:
            vertical: Vertical name (e.g., "flights", "hotels")
            
        Returns:
            List of handlers for the vertical
        """
        return self._vertical_handlers.get(vertical, []).copy()

