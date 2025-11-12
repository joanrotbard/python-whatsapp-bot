"""Adapters (Infrastructure Layer).

Adapters that adapt between different interfaces and patterns.
These handle integration and compatibility concerns.
"""
from app.infrastructure.adapters.message_handler import MessageHandler

__all__ = [
    "MessageHandler",
]

