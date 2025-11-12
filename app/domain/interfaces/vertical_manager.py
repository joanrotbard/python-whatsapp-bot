"""Interface for vertical managers (Registry Pattern).

Manages different travel verticals (flights, hotels, etc.)
and routes function calls to appropriate handlers.
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, List

from app.domain.interfaces.function_handler import IFunctionHandler


class IVerticalManager(ABC):
    """
    Interface for vertical managers following Registry Pattern.
    
    Manages registration and routing of function handlers
    for different travel verticals.
    """
    
    @abstractmethod
    def register_handler(self, handler: IFunctionHandler, vertical: str) -> None:
        """
        Register a function handler for a specific vertical.
        
        Args:
            handler: Function handler instance
            vertical: Vertical name (e.g., "flights", "hotels")
            
        Raises:
            ValueError: If handler is invalid
        """
        pass
    
    @abstractmethod
    def get_handler(self, function_name: str) -> Optional[IFunctionHandler]:
        """
        Get handler for a specific function name.
        
        Args:
            function_name: Name of the function to handle
            
        Returns:
            Function handler if found, None otherwise
        """
        pass
    
    @abstractmethod
    def get_all_handlers(self) -> Dict[str, IFunctionHandler]:
        """
        Get all registered handlers.
        
        Returns:
            Dictionary mapping function names to handlers
        """
        pass
    
    @abstractmethod
    def get_handlers_by_vertical(self, vertical: str) -> List[IFunctionHandler]:
        """
        Get all handlers for a specific vertical.
        
        Args:
            vertical: Vertical name (e.g., "flights", "hotels")
            
        Returns:
            List of handlers for the vertical
        """
        pass

