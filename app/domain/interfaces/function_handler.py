"""Interface for function handlers (Strategy Pattern).

This allows different verticals (flights, hotels, etc.) to implement
their own function handlers independently.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class IFunctionHandler(ABC):
    """
    Interface for function handlers following Strategy Pattern.
    
    Each vertical (flights, hotels, etc.) implements this interface
    to handle their specific function calls from the AI assistant.
    """
    
    @abstractmethod
    def get_function_name(self) -> str:
        """
        Get the name of the function this handler processes.
        
        Returns:
            Function name (must match OpenAI function name)
        """
        pass
    
    @abstractmethod
    def handle(self, parameters: Dict[str, Any], user_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle a function call from the AI assistant.
        
        Args:
            parameters: Function parameters from AI assistant
            user_id: Unique user identifier
            context: Optional context (e.g., conversation history)
            
        Returns:
            Result dictionary to be returned to AI assistant
            
        Raises:
            ValueError: If parameters are invalid
            Exception: If function execution fails
        """
        pass
    
    @abstractmethod
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """
        Validate function parameters before execution.
        
        Args:
            parameters: Function parameters to validate
            
        Returns:
            True if parameters are valid, False otherwise
        """
        pass

