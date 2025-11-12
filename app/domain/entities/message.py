"""Message domain entity."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Message:
    """Domain entity representing a message."""
    
    user_id: str
    user_name: str
    message_id: str
    message_body: str
    provider: str  # e.g., "whatsapp", "telegram"
    timestamp: Optional[float] = None
    
    def __post_init__(self):
        """Validate message entity."""
        if not self.user_id:
            raise ValueError("user_id is required")
        if not self.message_body:
            raise ValueError("message_body is required")

