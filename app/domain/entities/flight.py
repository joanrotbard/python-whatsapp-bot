"""Flight domain entities."""
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime


@dataclass
class Flight:
    """Domain entity representing a flight option."""
    
    flight_id: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    airline: str
    price: float
    currency: str = "USD"
    available_seats: int = 0
    flight_number: str = ""
    duration_minutes: Optional[int] = None
    
    def __post_init__(self):
        """Validate flight entity."""
        if not self.flight_id:
            raise ValueError("flight_id is required")
        if not self.origin:
            raise ValueError("origin is required")
        if not self.destination:
            raise ValueError("destination is required")
        if self.price < 0:
            raise ValueError("price must be non-negative")


@dataclass
class Booking:
    """Domain entity representing a flight booking."""
    
    booking_id: str
    user_id: str
    flight_id: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    passengers: int
    total_price: float
    currency: str = "USD"
    status: str = "confirmed"  # confirmed, cancelled, completed
    booking_date: Optional[datetime] = None
    airline: Optional[str] = None
    flight_number: Optional[str] = None
    
    def __post_init__(self):
        """Validate booking entity."""
        if not self.booking_id:
            raise ValueError("booking_id is required")
        if not self.user_id:
            raise ValueError("user_id is required")
        if not self.flight_id:
            raise ValueError("flight_id is required")
        if self.passengers <= 0:
            raise ValueError("passengers must be positive")
        if self.total_price < 0:
            raise ValueError("total_price must be non-negative")
        if self.status not in ["confirmed", "cancelled", "completed"]:
            raise ValueError(f"Invalid status: {self.status}")


@dataclass
class TravelHistory:
    """Domain entity representing a user's travel history."""
    
    user_id: str
    bookings: List[Booking]
    
    def __post_init__(self):
        """Validate travel history entity."""
        if not self.user_id:
            raise ValueError("user_id is required")
        if not isinstance(self.bookings, list):
            raise ValueError("bookings must be a list")

