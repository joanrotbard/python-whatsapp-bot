"""Infrastructure providers - concrete implementations."""

from app.infrastructure.providers.whatsapp_provider import WhatsAppProvider
from app.infrastructure.providers.openai_provider import OpenAIProvider

# LangChain provider - optional import (will fail gracefully if dependencies not installed)
try:
    from app.infrastructure.providers.langchain_provider import LangChainProvider
    __all__ = [
        "WhatsAppProvider",
        "OpenAIProvider",
        "LangChainProvider",
    ]
except ImportError:
    # LangChain not available - app can still run with OpenAI provider
    LangChainProvider = None
    __all__ = [
        "WhatsAppProvider",
        "OpenAIProvider",
    ]

