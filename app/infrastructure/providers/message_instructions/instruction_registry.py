"""Message instructions for different use cases.

This module provides extensible instructions that can be added to tool results
to guide the LLM on how to format responses for specific use cases.

Uses the Strategy pattern to allow easy extension for new use cases.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MessageInstruction(ABC):
    """
    Abstract base class for message instructions.
    
    Each instruction provides guidance for formatting responses
    for a specific use case or tool.
    """
    
    @abstractmethod
    def applies_to(self, tool_name: str, result: Dict[str, Any]) -> bool:
        """
        Check if this instruction applies to the given tool result.
        
        Args:
            tool_name: Name of the tool that produced the result
            result: The parsed result dictionary
            
        Returns:
            True if this instruction applies, False otherwise
        """
        pass
    
    @abstractmethod
    def get_instruction(self) -> str:
        """
        Get the instruction text to be included in the response.
        
        Returns:
            Instruction text string
        """
        pass


class MessageInstructionRegistry:
    """
    Registry for message instructions.
    
    Uses the Registry pattern to allow extensible instruction management
    without modifying the main provider code.
    """
    
    def __init__(self):
        """Initialize the registry with default instructions."""
        self._instructions: list[MessageInstruction] = []
        self._register_default_instructions()
    
    def _register_default_instructions(self):
        """Register default instructions."""
        # Import here to avoid circular dependencies
        from app.infrastructure.providers.message_instructions.flight_search_instruction import (
            FlightSearchMessageInstruction
        )
        self.register(FlightSearchMessageInstruction())
    
    def register(self, instruction: MessageInstruction):
        """
        Register a new message instruction.
        
        Args:
            instruction: Instruction instance to register
        """
        self._instructions.append(instruction)
        logger.debug(f"Registered message instruction: {instruction.__class__.__name__}")
    
    def get_instruction(self, tool_name: str, result: Dict[str, Any]) -> Optional[str]:
        """
        Get the appropriate instruction for the given tool result.
        
        Args:
            tool_name: Name of the tool that produced the result
            result: The parsed result dictionary
            
        Returns:
            Instruction text if found, None otherwise
        """
        for instruction in self._instructions:
            try:
                if instruction.applies_to(tool_name, result):
                    logger.debug(f"Using instruction {instruction.__class__.__name__} for tool {tool_name}")
                    return instruction.get_instruction()
            except Exception as e:
                logger.warning(
                    f"Instruction {instruction.__class__.__name__} failed for tool {tool_name}: {e}"
                )
                continue
        
        return None


# Global registry instance
_instruction_registry = None


def get_instruction_registry() -> MessageInstructionRegistry:
    """
    Get the global instruction registry instance (singleton pattern).
    
    Returns:
        The global MessageInstructionRegistry instance
    """
    global _instruction_registry
    if _instruction_registry is None:
        _instruction_registry = MessageInstructionRegistry()
    return _instruction_registry

