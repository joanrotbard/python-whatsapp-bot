"""Message instructions for different use cases.

This module provides backward compatibility imports.
New instructions should be added in the message_instructions/ directory.
"""
# Backward compatibility - import from new location
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

