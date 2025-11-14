"""Parser for flight search responses from Starlings API.

This module provides functions to parse and transform flight search responses
into clean, structured data suitable for display and context storage.

This is a Python port of the TypeScript parseFlightSearchResponse function.
"""
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def merge_date_time(date_str: str, time_str: str) -> str:
    """
    Merge date and time into ISO format string.
    
    Args:
        date_str: Date string (YYYY-MM-DD)
        time_str: Time string (HH:mm)
        
    Returns:
        Combined datetime string (YYYY-MM-DDTHH:mm:00)
    """
    return f"{date_str}T{time_str}:00"


def calculate_total_duration_with_layovers(segments: List[Dict[str, Any]]) -> int:
    """
    Calculate total flight duration including layover times between segments.
    
    The total duration is calculated as the difference between:
    - Departure time of the first segment
    - Arrival time of the last segment
    
    This automatically includes all flight times and layover times.
    
    Args:
        segments: List of segment dictionaries, each with 'departureDateTime' and 'arrivalDateTime'
        
    Returns:
        Total duration in minutes including layovers, or 0 if calculation fails
    """
    if not segments or len(segments) == 0:
        return 0
    
    # Get first and last segments
    first_segment = segments[0]
    last_segment = segments[-1]
    
    # Get departure time of first segment
    departure_str = first_segment.get('departureDateTime', '')
    # Get arrival time of last segment
    arrival_str = last_segment.get('arrivalDateTime', '')
    
    if not departure_str or not arrival_str:
        # Fallback: if datetime strings are missing, try to use segment durations
        logger.warning("Missing departure or arrival datetime, falling back to sum of segment durations")
        total_flight_time = sum(seg.get('duration', 0) for seg in segments)
        
        # Try to calculate layovers if we have datetime info for some segments
        total_layover_time = 0
        for i in range(len(segments) - 1):
            current_segment = segments[i]
            next_segment = segments[i + 1]
            
            curr_arrival = current_segment.get('arrivalDateTime', '')
            next_departure = next_segment.get('departureDateTime', '')
            
            if curr_arrival and next_departure:
                try:
                    arrival_dt = datetime.fromisoformat(curr_arrival.replace('Z', '+00:00'))
                    departure_dt = datetime.fromisoformat(next_departure.replace('Z', '+00:00'))
                    layover_delta = departure_dt - arrival_dt
                    layover_minutes = int(layover_delta.total_seconds() / 60)
                    if layover_minutes > 0:
                        total_layover_time += layover_minutes
                except (ValueError, AttributeError):
                    pass
        
        return total_flight_time + total_layover_time
    
    try:
        # Parse datetime strings (format: YYYY-MM-DDTHH:mm:00)
        departure_dt = datetime.fromisoformat(departure_str.replace('Z', '+00:00'))
        arrival_dt = datetime.fromisoformat(arrival_str.replace('Z', '+00:00'))
        
        # Calculate total duration (difference in minutes)
        duration_delta = arrival_dt - departure_dt
        total_minutes = int(duration_delta.total_seconds() / 60)
        
        if total_minutes < 0:
            logger.error(
                f"Negative duration calculated: {total_minutes} minutes "
                f"from {departure_str} to {arrival_str}. Falling back to sum of segment durations."
            )
            # Fallback to sum of durations
            return sum(seg.get('duration', 0) for seg in segments)
        
        logger.debug(
            f"Total duration calculated: {total_minutes} minutes "
            f"(from {departure_str} to {arrival_str})"
        )
        
        return total_minutes
        
    except (ValueError, AttributeError) as e:
        logger.error(f"Error parsing datetime for duration calculation: {e}")
        # Fallback: sum of segment durations (without layovers)
        fallback_duration = sum(seg.get('duration', 0) for seg in segments)
        logger.warning(f"Using fallback duration calculation: {fallback_duration} minutes")
        return fallback_duration


def parse_flight_search_response(
    response: Dict[str, Any],
    sort_order: str = 'cheapest',
    limit: int = 5
) -> Dict[str, Any]:
    """
    Parse flight search response from Starlings API and transform into clean list of flight options.
    
    This is a Python port of the TypeScript parseFlightSearchResponse function.
    
    Args:
        response: Flight search response from Starlings API (should have 'Fares' key)
        sort_order: Sort order: 'cheapest' (default) or 'most_expensive'
        limit: Maximum number of results to return (default: 5)
        
    Returns:
        Dictionary containing:
            - options: List of parsed flight options (limited)
            - allFlightsContext: List of string representations of all flights
            - totalCount: Total number of flights found
            
    Raises:
        ValueError: If response structure is invalid or no fares found
    """
    # Validate response structure
    if not response or 'Fares' not in response:
        raise ValueError('Invalid response: response.Fares is missing')
    
    fares = response.get('Fares', [])
    if not isinstance(fares, list):
        raise ValueError('Invalid response: response.Fares is not an array')
    
    if len(fares) == 0:
        raise ValueError('No fares found in response')
    
    parsed_options = []
    
    # Parse each fare
    for fare in fares:
        # Validate required fields
        if not fare.get('PaxFares') or len(fare.get('PaxFares', [])) == 0:
            continue  # Skip fares without passenger information
        
        # Use first passenger group (PaxFares[0])
        pax = fare['PaxFares'][0]
        
        # Extract segments from legs
        segments = []
        legs_info = []
        
        for leg in fare.get('Legs', []):
            if not leg.get('Options') or len(leg.get('Options', [])) == 0:
                continue
            
            # Use the first option (Options[0])
            option = leg['Options'][0]
            
            # Extract leg information
            legs_info.append({
                'legNumber': leg.get('LegNumber'),
                'flightOptionID': option.get('FlightOptionID'),
                'optionDuration': option.get('OptionDuration')
            })
            
            # Extract segments from this option
            for segment in option.get('Segments', []):
                departure = segment.get('Departure', {})
                arrival = segment.get('Arrival', {})
                
                # Extract city information if available
                departure_city = departure.get('City', '') or departure.get('CityName', '') or ''
                arrival_city = arrival.get('City', '') or arrival.get('CityName', '') or ''
                
                segments.append({
                    'airline': segment.get('Airline', ''),
                    'operatingAirline': segment.get('OperatingAirline', ''),
                    'flightNumber': segment.get('FlightNumber', 0),
                    'bookingClass': segment.get('BookingClass', ''),
                    'cabinClass': segment.get('CabinClass', ''),
                    'departureAirport': departure.get('AirportCode', ''),
                    'departureCity': departure_city,
                    'arrivalAirport': arrival.get('AirportCode', ''),
                    'arrivalCity': arrival_city,
                    'departureDateTime': merge_date_time(
                        departure.get('Date', ''),
                        departure.get('Time', '')
                    ),
                    'arrivalDateTime': merge_date_time(
                        arrival.get('Date', ''),
                        arrival.get('Time', '')
                    ),
                    'duration': segment.get('Duration', 0),
                    'baggage': segment.get('Baggage', ''),
                    'brandName': segment.get('BrandName')
                })
        
        # Parse price
        price = {
            'base': fare.get('FareAmount', 0),
            'taxes': fare.get('TaxAmount', 0),
            'service': fare.get('ServiceAmount', 0),
            'commission': fare.get('CommissionAmount', 0),
            'total': fare.get('TotalAmount', 0),
            'totalWithFees': fare.get('TotalAmountWithFees', 0),
            'currency': fare.get('Currency', ''),
            'paxCount': pax.get('Count', 0)
        }
        
        # Determine total amount (use TotalAmountWithFees if available, otherwise TotalAmount)
        total_amount = fare.get('TotalAmountWithFees') or fare.get('TotalAmount') or 0
        
        # FareID becomes the id
        fare_id = fare.get('FareID') or fare.get('recommendation_id') or f"fare_{hash(str(fare)) % 1000000}"
        
        # Separate segments by leg (outbound vs return) and store OptionDuration for each leg
        outbound_segments = []
        return_segments = []
        outbound_option_duration = None
        return_option_duration = None
        
        # Track which segment belongs to which leg
        segment_idx = 0
        for leg in fare.get('Legs', []):
            if not leg.get('Options') or len(leg.get('Options', [])) == 0:
                continue
            
            option = leg['Options'][0]
            leg_number = leg.get('LegNumber', 1)
            num_segments_in_leg = len(option.get('Segments', []))
            option_duration = option.get('OptionDuration')
            
            # Leg 1 is outbound, Leg 2+ is return
            if leg_number == 1:
                # Outbound leg
                outbound_segments = segments[segment_idx:segment_idx + num_segments_in_leg]
                outbound_option_duration = option_duration
            else:
                # Return leg
                return_segments = segments[segment_idx:segment_idx + num_segments_in_leg]
                return_option_duration = option_duration
            
            segment_idx += num_segments_in_leg
        
        # Create parsed flight option
        parsed_option = {
            'id': fare_id,
            'validatingCarrier': fare.get('ValidatingCarrier', ''),
            'totalAmount': total_amount,
            'currency': fare.get('Currency', ''),
            'lastTicketingDate': fare.get('LastTicketingDate', ''),
            'segments': segments,
            'outbound_segments': outbound_segments,
            'return_segments': return_segments,
            'is_round_trip': len(legs_info) > 1,
            'price': price,
            'recommendation_id': fare.get('recommendation_id', ''),
            'approval_evaluation_status': fare.get('approval_evaluation_status', ''),
            'legs': legs_info,
            'outbound_option_duration': outbound_option_duration,
            'return_option_duration': return_option_duration
        }
        
        parsed_options.append(parsed_option)
    
    # Sort by totalAmount
    parsed_options.sort(
        key=lambda x: x['totalAmount'],
        reverse=(sort_order == 'most_expensive')
    )
    
    # Convert all flights to context strings
    all_flights_context = []
    for option in parsed_options:
        segments = option['segments']
        is_round_trip = option.get('is_round_trip', False)
        outbound_segments = option.get('outbound_segments', segments)
        return_segments = option.get('return_segments', [])
        # Get OptionDuration values stored in parsed_option
        outbound_option_duration = option.get('outbound_option_duration')
        return_option_duration = option.get('return_option_duration')
        
        # Helper function to format segments
        def format_segments_list(seg_list, leg_prefix=""):
            seg_info = []
            for idx, seg in enumerate(seg_list):
                flight_number = f"{seg.get('airline', '')}{seg.get('flightNumber', '')}"
                departure_airport = seg.get('departureAirport', '')
                departure_city = seg.get('departureCity', '')
                if departure_city:
                    departure_info = f"{departure_airport}({departure_city})@{seg.get('departureDateTime', '')}"
                else:
                    departure_info = f"{departure_airport}@{seg.get('departureDateTime', '')}"
                arrival_airport = seg.get('arrivalAirport', '')
                arrival_city = seg.get('arrivalCity', '')
                if arrival_city:
                    arrival_info = f"{arrival_airport}({arrival_city})@{seg.get('arrivalDateTime', '')}"
                else:
                    arrival_info = f"{arrival_airport}@{seg.get('arrivalDateTime', '')}"
                # Include airline information in segment
                airline_code = seg.get('airline', '')
                operating_airline = seg.get('operatingAirline', '')
                airline_info = airline_code
                if operating_airline and operating_airline != airline_code:
                    airline_info = f"{airline_code}(op:{operating_airline})"
                
                seg_str = (
                    leg_prefix + "Seg" + str(idx + 1) + ":{" +
                    "Airline:" + airline_info + "," +
                    "FlightNumber:" + flight_number + "," +
                    "Departure:" + departure_info + "," +
                    "Arrival:" + arrival_info + "," +
                    "Duration:" + str(seg.get('duration', 0)) + "," +
                    "Baggage:" + str(seg.get('baggage', 'N/A')) + "}"
                )
                seg_info.append(seg_str)
            return '|'.join(seg_info)
        
        # Format outbound segments
        outbound_segments_str = format_segments_list(outbound_segments, "Outbound")
        return_segments_str = format_segments_list(return_segments, "Return") if return_segments else ""
        
        # Extract unique airlines from all segments
        def extract_airlines(seg_list):
            """Extract unique airline codes from segments."""
            airlines = set()
            for seg in seg_list:
                airline = seg.get('airline', '').strip()
                operating_airline = seg.get('operatingAirline', '').strip()
                if airline:
                    airlines.add(airline)
                if operating_airline and operating_airline != airline:
                    airlines.add(operating_airline)
            return sorted(list(airlines))  # Sort for consistency
        
        # Extract airlines for outbound, return, and overall
        outbound_airlines = extract_airlines(outbound_segments)
        return_airlines = extract_airlines(return_segments) if return_segments else []
        all_airlines = extract_airlines(segments)
        
        # Format airlines as comma-separated string
        outbound_airlines_str = ','.join(outbound_airlines) if outbound_airlines else 'N/A'
        return_airlines_str = ','.join(return_airlines) if return_airlines else 'N/A'
        all_airlines_str = ','.join(all_airlines) if all_airlines else 'N/A'
        
        # Calculate stats for outbound - use OptionDuration directly from API
        outbound_num_segments = len(outbound_segments)
        outbound_num_stops = max(0, outbound_num_segments - 1)
        
        # Use OptionDuration from API if available, otherwise calculate as fallback
        if outbound_option_duration and outbound_option_duration > 0:
            outbound_duration = outbound_option_duration
            logger.debug(f"Using API OptionDuration for outbound: {outbound_duration} minutes")
        else:
            outbound_duration = calculate_total_duration_with_layovers(outbound_segments)
            logger.warning(f"OptionDuration not available for outbound, calculated: {outbound_duration} minutes")
        
        outbound_first = outbound_segments[0] if outbound_segments else {}
        outbound_last = outbound_segments[-1] if outbound_segments else {}
        
        # Calculate stats for return - use OptionDuration directly from API
        return_num_segments = len(return_segments)
        return_num_stops = max(0, return_num_segments - 1) if return_segments else 0
        
        # Use OptionDuration from API if available, otherwise calculate as fallback
        if return_segments:
            if return_option_duration and return_option_duration > 0:
                return_duration = return_option_duration
                logger.debug(f"Using API OptionDuration for return: {return_duration} minutes")
            else:
                return_duration = calculate_total_duration_with_layovers(return_segments)
                logger.warning(f"OptionDuration not available for return, calculated: {return_duration} minutes")
        else:
            return_duration = 0
        
        return_first = return_segments[0] if return_segments else {}
        return_last = return_segments[-1] if return_segments else {}
        
        # Overall stats (for round-trip: sum of outbound + return durations)
        num_segments = len(segments)
        num_stops = max(0, num_segments - 1)
        if is_round_trip and return_segments:
            # For round-trip, total duration is sum of outbound and return (each already includes layovers)
            total_duration = outbound_duration + return_duration
            logger.debug(f"Round-trip total duration: {total_duration} minutes (outbound: {outbound_duration}, return: {return_duration})")
        else:
            # For one-way, calculate total duration including layovers
            total_duration = calculate_total_duration_with_layovers(segments)
            logger.debug(f"One-way total duration: {total_duration} minutes")
        
        # Check if all segments have baggage
        all_have_baggage = all(
            seg.get('baggage') and str(seg.get('baggage', '')).strip().upper() not in ['', 'NONE', 'NO', '0']
            for seg in segments
        ) if segments else False
        baggage_status = "HasBaggage" if all_have_baggage else "NoBaggage"
        
        # Get route information
        first_segment = segments[0] if segments else {}
        last_segment = segments[-1] if segments else {}
        origin_airport = first_segment.get('departureAirport', '')
        origin_city = first_segment.get('departureCity', '')
        destination_airport = last_segment.get('arrivalAirport', '')
        destination_city = last_segment.get('arrivalCity', '')
        departure_datetime = first_segment.get('departureDateTime', '')
        arrival_datetime = last_segment.get('arrivalDateTime', '')
        
        # Format route with cities if available
        if origin_city and destination_city:
            route_info = f"{origin_airport}({origin_city})->{destination_airport}({destination_city})"
        elif origin_city:
            route_info = f"{origin_airport}({origin_city})->{destination_airport}"
        elif destination_city:
            route_info = f"{origin_airport}->{destination_airport}({destination_city})"
        else:
            route_info = f"{origin_airport}->{destination_airport}"
        
        # Format policy status
        policy_status = option.get('approval_evaluation_status', 'unknown')
        if policy_status == 'in_policy':
            policy_display = 'InPolicy'
        elif policy_status == 'requires_approval':
            policy_display = 'RequiresApproval'
        else:
            policy_display = policy_status
        
        # Build comprehensive string with improved format
        # For round-trip, include separate outbound and return information
        if is_round_trip and return_segments:
            context_str = (
                f"FareID:{option['id']}|"
                f"FlightType:RoundTrip|"
                f"Route:{route_info}|"
                f"TotalPrice:{option['totalAmount']}|"
                f"Currency:{option['currency']}|"
                f"TotalDuration:{total_duration}|"
                f"Airlines:{all_airlines_str}|"
                f"OutboundAirlines:{outbound_airlines_str}|"
                f"OutboundSegments:{outbound_num_segments}|"
                f"OutboundStops:{outbound_num_stops}|"
                f"OutboundDuration:{outbound_duration}|"
                f"OutboundDeparture:{outbound_first.get('departureDateTime', '')}|"
                f"OutboundArrival:{outbound_last.get('arrivalDateTime', '')}|"
                f"OutboundSegments:[{outbound_segments_str}]|"
                f"ReturnAirlines:{return_airlines_str}|"
                f"ReturnSegments:{return_num_segments}|"
                f"ReturnStops:{return_num_stops}|"
                f"ReturnDuration:{return_duration}|"
                f"ReturnDeparture:{return_first.get('departureDateTime', '')}|"
                f"ReturnArrival:{return_last.get('arrivalDateTime', '')}|"
                f"ReturnSegments:[{return_segments_str}]|"
                f"PolicyStatus:{policy_display}|"
                f"LastTicketingDate:{option['lastTicketingDate']}|"
                f"BaggageStatus:{baggage_status}|"
                f"ValidatingCarrier:{option['validatingCarrier']}|"
                f"RecommendationID:{option['recommendation_id']}"
            )
        else:
            # One-way flight
            segments_info_str = format_segments_list(segments)
            context_str = (
                f"FareID:{option['id']}|"
                f"FlightType:OneWay|"
                f"Route:{route_info}|"
                f"Departure:{departure_datetime}|"
                f"Arrival:{arrival_datetime}|"
                f"TotalDuration:{total_duration}|"
                f"NumSegments:{num_segments}|"
                f"NumStops:{num_stops}|"
                f"Airlines:{all_airlines_str}|"
                f"Segments:[{segments_info_str}]|"
                f"Price:{option['totalAmount']}|"
                f"Currency:{option['currency']}|"
                f"PolicyStatus:{policy_display}|"
                f"LastTicketingDate:{option['lastTicketingDate']}|"
                f"BaggageStatus:{baggage_status}|"
                f"ValidatingCarrier:{option['validatingCarrier']}|"
                f"RecommendationID:{option['recommendation_id']}"
            )
        all_flights_context.append(context_str)
    
    # Return limited results
    limited_options = parsed_options[:limit]
    
    return {
        'options': limited_options,
        'allFlightsContext': all_flights_context,
        'totalCount': len(parsed_options)
    }


def get_most_expensive_flights(
    response: Dict[str, Any],
    limit: int = 5
) -> Dict[str, Any]:
    """
    Get the most expensive flights from parsed response.
    
    Args:
        response: Flight search response from Starlings API
        limit: Maximum number of results to return (default: 5)
        
    Returns:
        Dictionary containing parsed flight options sorted by most expensive
    """
    return parse_flight_search_response(response, 'most_expensive', limit)


def get_all_flights(
    response: Dict[str, Any],
    sort_order: str = 'cheapest'
) -> Dict[str, Any]:
    """
    Get all flights (no limit) sorted by price.
    
    Args:
        response: Flight search response from Starlings API
        sort_order: Sort order: 'cheapest' (default) or 'most_expensive'
        
    Returns:
        Dictionary containing all parsed flight options
    """
    return parse_flight_search_response(response, sort_order, float('inf'))

