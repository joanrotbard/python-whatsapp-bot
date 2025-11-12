"""Domain entities - core business objects."""
from app.domain.entities.message import Message
from app.domain.entities.flight import Flight, Booking, TravelHistory

__all__ = [
    "Message",
    "Flight",
    "Booking",
    "TravelHistory",
]
