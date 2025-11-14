"""Response parsers for tool results.

This module provides backward compatibility imports.
New parsers should be added in the response_parsers/ directory.
"""
# Backward compatibility - import from new location
from app.infrastructure.providers.response_parsers import (
    ResponseParser,
    ResponseParserRegistry,
    get_parser_registry
)

__all__ = [
    "ResponseParser",
    "ResponseParserRegistry",
    "get_parser_registry"
]

