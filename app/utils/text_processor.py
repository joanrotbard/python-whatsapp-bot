"""Text processing utilities for WhatsApp formatting."""
import re
from typing import Pattern


class WhatsAppTextProcessor:
    """Utility class for processing text for WhatsApp."""
    
    # Compile regex patterns once for better performance
    BRACKET_PATTERN: Pattern = re.compile(r"\【.*?\】")
    BOLD_PATTERN: Pattern = re.compile(r"\*\*(.*?)\*\*")
    
    @classmethod
    def process(cls, text: str) -> str:
        """
        Process text for WhatsApp formatting.
        
        Removes brackets and converts markdown bold (**text**) to WhatsApp bold (*text*).
        
        Args:
            text: Raw text to process
            
        Returns:
            Processed text formatted for WhatsApp
        """
        # Remove brackets
        processed = cls.BRACKET_PATTERN.sub("", text).strip()
        
        # Convert **bold** to *bold* (WhatsApp format)
        processed = cls.BOLD_PATTERN.sub(r"*\1*", processed)
        
        return processed

