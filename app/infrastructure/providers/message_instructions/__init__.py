"""Message instructions for different use cases.

This package provides extensible message instructions for tool results.
"""
# Export main classes and functions
from app.infrastructure.providers.message_instructions.instruction_registry import (
    MessageInstruction,
    MessageInstructionRegistry,
    get_instruction_registry
)

__all__ = [
    "MessageInstruction",
    "MessageInstructionRegistry",
    "get_instruction_registry"
]
