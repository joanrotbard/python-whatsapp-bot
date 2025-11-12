"""Mock implementation of travel API client for development/testing."""
import logging
import uuid
from typing import List, Optional
from datetime import datetime, timedelta
import random

from app.domain.interfaces.travel_api_client import ITravelAPIClient
from app.domain.entities.flight import Flight, Booking, TravelHistory


logger = logging.getLogger(__name__)


class MockTravelAPIClient(ITravelAPIClient):
    """
    Mock implementation of travel API client.
    
    Returns realistic mock data for development and testing.
    In production, this would be replaced with actual API client.
    """
    
    def __init__(self):
        """Initialize mock client with in-memory storage."""
        self._bookings: dict[str, Booking] = {}
        self._user_bookings: dict[str, List[str]] = {}  # user_id -> [booking_ids]
        self._logger = logging.getLogger(__name__)
        self._initialize_mock_data()
    
    def _initialize_mock_data(self) -> None:
        """Initialize with some sample bookings for testing."""
        # Create sample bookings for demo user
        demo_user_id = "demo_user_123"
        sample_origins = ["JFK", "LAX", "SFO", "ORD", "MIA"]
        sample_destinations = ["LHR", "CDG", "NRT", "DXB", "SYD"]
        airlines = ["American Airlines", "United Airlines", "Delta", "British Airways", "Lufthansa"]
        
        for i in range(3):
            booking_id = f"BK{str(uuid.uuid4())[:8].upper()}"
            flight_id = f"FL{str(uuid.uuid4())[:8].upper()}"
            origin = random.choice(sample_origins)
            destination = random.choice(sample_destinations)
            
            # Mix of past and future bookings
            if i == 0:
                departure = datetime.now() - timedelta(days=30)
                arrival = departure + timedelta(hours=6)
                status = "completed"
            elif i == 1:
                departure = datetime.now() + timedelta(days=15)
                arrival = departure + timedelta(hours=7)
                status = "confirmed"
            else:
                departure = datetime.now() + timedelta(days=45)
                arrival = departure + timedelta(hours=8)
                status = "confirmed"
            
            booking = Booking(
                booking_id=booking_id,
                user_id=demo_user_id,
                flight_id=flight_id,
                origin=origin,
                destination=destination,
                departure_time=departure,
                arrival_time=arrival,
                passengers=random.randint(1, 3),
                total_price=round(random.uniform(300, 1500), 2),
                currency="USD",
                status=status,
                booking_date=departure - timedelta(days=60),
                airline=random.choice(airlines),
                flight_number=f"{random.choice(['AA', 'UA', 'DL', 'BA', 'LH'])}{random.randint(100, 9999)}"
            )
            
            self._bookings[booking_id] = booking
            if demo_user_id not in self._user_bookings:
                self._user_bookings[demo_user_id] = []
            self._user_bookings[demo_user_id].append(booking_id)
    
    def search_flights(
        self,
        origin: str,
        destination: str,
        date: str,
        passengers: int = 1,
        **kwargs
    ) -> List[Flight]:
        """
        Search for flight options (mock implementation).
        
        Args:
            origin: Origin airport/city code
            destination: Destination airport/city code
            date: Travel date (ISO format or YYYY-MM-DD)
            passengers: Number of passengers
            **kwargs: Additional search parameters
            
        Returns:
            List of available flight options
        """
        self._logger.info(f"Mock: Searching flights {origin} -> {destination} on {date} for {passengers} passenger(s)")
        
        # Parse date
        try:
            if "T" in date:
                departure_date = datetime.fromisoformat(date.replace("Z", "+00:00"))
            else:
                departure_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            # Default to tomorrow if parsing fails
            departure_date = datetime.now() + timedelta(days=1)
        
        # Generate mock flight options
        airlines = ["American Airlines", "United Airlines", "Delta", "British Airways", "Lufthansa", "Emirates"]
        flights = []
        
        # Generate 3-5 flight options
        num_options = random.randint(3, 5)
        
        for i in range(num_options):
            # Vary departure times throughout the day
            departure_time = departure_date.replace(
                hour=random.randint(6, 22),
                minute=random.choice([0, 15, 30, 45])
            )
            
            # Flight duration between 2-12 hours
            duration_hours = random.uniform(2, 12)
            arrival_time = departure_time + timedelta(hours=duration_hours)
            
            # Price varies by time and airline
            base_price = random.uniform(200, 1200)
            price_multiplier = 1.0 + (i * 0.1)  # First option is cheapest
            total_price = round(base_price * price_multiplier * passengers, 2)
            
            flight = Flight(
                flight_id=f"FL{str(uuid.uuid4())[:8].upper()}",
                origin=origin.upper(),
                destination=destination.upper(),
                departure_time=departure_time,
                arrival_time=arrival_time,
                airline=random.choice(airlines),
                price=total_price,
                currency="USD",
                available_seats=random.randint(5, 50),
                flight_number=f"{random.choice(['AA', 'UA', 'DL', 'BA', 'LH', 'EK'])}{random.randint(100, 9999)}",
                duration_minutes=int(duration_hours * 60)
            )
            flights.append(flight)
        
        # Sort by price (cheapest first)
        flights.sort(key=lambda f: f.price)
        
        return flights
    
    def get_booking(self, booking_id: str, user_id: Optional[str] = None) -> Optional[Booking]:
        """
        Retrieve booking details (mock implementation).
        
        Args:
            booking_id: Unique booking identifier
            user_id: Optional user ID for validation
            
        Returns:
            Booking details if found, None otherwise
        """
        self._logger.info(f"Mock: Retrieving booking {booking_id}")
        
        booking = self._bookings.get(booking_id)
        
        if booking is None:
            return None
        
        # Validate user_id if provided
        if user_id and booking.user_id != user_id:
            self._logger.warning(f"Booking {booking_id} does not belong to user {user_id}")
            return None
        
        return booking
    
    def cancel_booking(self, booking_id: str, user_id: str, confirmation: bool = False) -> bool:
        """
        Cancel a booking (mock implementation).
        
        Args:
            booking_id: Unique booking identifier
            user_id: User ID for authorization
            confirmation: Whether cancellation is confirmed
            
        Returns:
            True if cancellation successful, False otherwise
            
        Raises:
            ValueError: If confirmation is False
        """
        if not confirmation:
            raise ValueError("Cancellation requires confirmation")
        
        self._logger.info(f"Mock: Cancelling booking {booking_id} for user {user_id}")
        
        booking = self._bookings.get(booking_id)
        
        if booking is None:
            self._logger.warning(f"Booking {booking_id} not found")
            return False
        
        if booking.user_id != user_id:
            self._logger.warning(f"Booking {booking_id} does not belong to user {user_id}")
            return False
        
        if booking.status == "cancelled":
            self._logger.warning(f"Booking {booking_id} is already cancelled")
            return False
        
        # Update booking status
        booking.status = "cancelled"
        self._bookings[booking_id] = booking
        
        return True
    
    def get_travel_history(self, user_id: str) -> TravelHistory:
        """
        Get user's travel history (mock implementation).
        
        Args:
            user_id: Unique user identifier
            
        Returns:
            User's travel history with all bookings
        """
        self._logger.info(f"Mock: Retrieving travel history for user {user_id}")
        
        booking_ids = self._user_bookings.get(user_id, [])
        bookings = [self._bookings[bid] for bid in booking_ids if bid in self._bookings]
        
        # Sort by departure time (most recent first)
        bookings.sort(key=lambda b: b.departure_time, reverse=True)
        
        return TravelHistory(user_id=user_id, bookings=bookings)
    
    def create_booking(
        self,
        user_id: str,
        flight_id: str,
        origin: str,
        destination: str,
        departure_time: datetime,
        arrival_time: datetime,
        passengers: int,
        total_price: float,
        airline: Optional[str] = None,
        flight_number: Optional[str] = None
    ) -> Booking:
        """
        Create a new booking (helper method for testing/demo).
        
        Args:
            user_id: User ID
            flight_id: Flight ID
            origin: Origin airport code
            destination: Destination airport code
            departure_time: Departure datetime
            arrival_time: Arrival datetime
            passengers: Number of passengers
            total_price: Total price
            airline: Airline name
            flight_number: Flight number
            
        Returns:
            Created booking
        """
        booking_id = f"BK{str(uuid.uuid4())[:8].upper()}"
        
        booking = Booking(
            booking_id=booking_id,
            user_id=user_id,
            flight_id=flight_id,
            origin=origin,
            destination=destination,
            departure_time=departure_time,
            arrival_time=arrival_time,
            passengers=passengers,
            total_price=total_price,
            currency="USD",
            status="confirmed",
            booking_date=datetime.now(),
            airline=airline,
            flight_number=flight_number
        )
        
        self._bookings[booking_id] = booking
        if user_id not in self._user_bookings:
            self._user_bookings[user_id] = []
        self._user_bookings[user_id].append(booking_id)
        
        return booking

