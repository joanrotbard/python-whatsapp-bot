"""Utility functions for flight search operations."""
import re
import json
import logging
import unicodedata
from datetime import datetime, date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from dateutil.parser import parse as dateutil_parse
except ImportError:
    dateutil_parse = None
    logger.warning("python-dateutil not installed, relative date parsing will be limited")


def format_date(date_string: Optional[str]) -> Optional[str]:
    """
    Format date string to YYYY-MM-DD format.
    
    Handles multiple input formats:
    - YYYY-MM-DD (already correct)
    - DD-MM-YYYY (converts)
    - Other formats (attempts to parse)
    
    Args:
        date_string: Date string in various formats
        
    Returns:
        Date string in YYYY-MM-DD format or None if invalid
    """
    if not date_string:
        return None
    
    # If already in correct format YYYY-MM-DD, return as is
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_string):
        return date_string
    
    # If in format DD-MM-YYYY, convert
    if re.match(r'^\d{2}-\d{2}-\d{4}$', date_string):
        parts = date_string.split('-')
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    
    # Try to parse other formats
    try:
        # Try common date formats
        for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%Y/%m/%d']:
            try:
                date_obj = datetime.strptime(date_string, fmt)
                return date_obj.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        # Last resort: try ISO format
        date_obj = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        return date_obj.strftime('%Y-%m-%d')
    except (ValueError, AttributeError):
        # If all parsing fails, return original (might be invalid)
        return date_string


def map_cabin_class(cabin_class: Optional[str]) -> str:
    """
    Map cabin class name to API code.
    
    Args:
        cabin_class: Cabin class name (economy, business, first, etc.)
        
    Returns:
        Cabin class code (Y, B, F, W) or 'Y' (Economy) as default
    """
    if not cabin_class:
        return 'Y'  # Default to Economy
    
    mapping = {
        'economy': 'Y',
        'business': 'B',
        'first': 'F',
        'premium economy': 'W',
        'premium': 'W',
        'y': 'Y',
        'b': 'B',
        'f': 'F',
        'w': 'W',
        'economy class': 'Y',
        'business class': 'B',
        'first class': 'F',
        'premium economy class': 'W'
    }
    
    return mapping.get(cabin_class.lower(), 'Y')  # Default to Economy


def extract_airport_code_with_llm(city_name: str) -> Optional[str]:
    """
    Use LLM to extract airport code from city name.
    
    Args:
        city_name: City name or location description
        
    Returns:
        3-character airport code or None if extraction fails
    """
    try:
        from openai import OpenAI
        from app.config.settings import Config
        
        if not Config.OPENAI_API_KEY:
            logger.warning("OpenAI API key not configured, cannot use LLM for airport code extraction")
            return None
        
        client = OpenAI(api_key=Config.OPENAI_API_KEY)
        
        prompt = f"""Extract the IATA airport code (3 letters) for the following city or location.
If the input is already a 3-letter code, return it as-is.
If it's a city name, return the most common/main airport code for that city.

Examples:
- "New York" -> "NYC"
- "Los Angeles" -> "LAX"
- "Buenos Aires" -> "EZE"
- "JFK" -> "JFK"
- "London" -> "LHR"
- "Paris" -> "CDG"

Input: {city_name}

Return ONLY the 3-letter airport code, nothing else:"""
        
        response = client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts IATA airport codes from city names. Always return exactly 3 uppercase letters."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=10
        )
        
        code = response.choices[0].message.content.strip().upper()
        
        # Validate it's a 3-letter code
        if len(code) == 3 and code.isalpha():
            logger.info(f"LLM extracted airport code: {city_name} -> {code}")
            return code
        else:
            logger.warning(f"LLM returned invalid airport code: {code} for input: {city_name}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to extract airport code with LLM: {e}")
        return None


def normalize_airport_code(airport_input: str, use_llm: bool = True) -> str:
    """
    Normalize airport code to exactly 3 uppercase characters.
    
    Handles:
    - Already 3-letter codes (JFK, LAX, etc.)
    - City names (uses LLM or fallback mappings)
    - Mixed case codes
    
    Args:
        airport_input: Airport code or city name
        use_llm: Whether to use LLM for city name extraction (default: True)
        
    Returns:
        3-character uppercase airport code
        
    Raises:
        ValueError: If cannot extract valid 3-character code
    """
    if not airport_input:
        raise ValueError("Airport code cannot be empty")
    
    # Remove whitespace and convert to uppercase
    code = airport_input.strip().upper()
    
    # If it's already 3 characters, return it
    if len(code) == 3 and code.isalpha():
        return code
    
    # Try to extract 3-letter code from input
    # Look for 3 consecutive uppercase letters
    match = re.search(r'[A-Z]{3}', code)
    if match:
        return match.group(0)
    
    # Try LLM extraction first if enabled
    if use_llm:
        llm_code = extract_airport_code_with_llm(airport_input)
        if llm_code:
            return llm_code
    
    # Fallback: Common city to airport code mappings
    city_mappings = {
        'NEW YORK': 'NYC',
        'NYC': 'NYC',
        'NEW YORK CITY': 'NYC',
        'LOS ANGELES': 'LAX',
        'LA': 'LAX',
        'SAN FRANCISCO': 'SFO',
        'SF': 'SFO',
        'CHICAGO': 'ORD',
        'LONDON': 'LHR',
        'PARIS': 'CDG',
        'MADRID': 'MAD',
        'BARCELONA': 'BCN',
        'BUENOS AIRES': 'EZE',
        'BA': 'EZE',
        'CÓRDOBA': 'COR',
        'CORDOBA': 'COR',
        'MENDOZA': 'MDZ',
        'ROME': 'FCO',
        'MILAN': 'MXP',
        'TOKYO': 'NRT',
        'DUBAI': 'DXB',
        'SYDNEY': 'SYD',
        'MELBOURNE': 'MEL',
    }
    
    # Check city mappings
    normalized_input = code.replace(' ', '').replace('-', '')
    if normalized_input in city_mappings:
        return city_mappings[normalized_input]
    
    # Check if input contains a known city (case-insensitive partial match)
    normalized_input_lower = normalized_input.lower()
    for city, code in city_mappings.items():
        if city.lower() in normalized_input_lower or normalized_input_lower in city.lower():
            return code
    
    # If we can't find a valid code, try to use first 3 letters
    # This is a fallback - might not be accurate
    if len(code) >= 3:
        return code[:3]
    
    raise ValueError(f"Cannot extract valid 3-character airport code from: {airport_input}")


def parse_relative_date(date_string: str) -> Optional[date]:
    """
    Parse relative date expressions like "next monday", "tomorrow", "next week", etc.
    
    Supports both English and Spanish expressions:
    - "tomorrow" / "mañana"
    - "next monday" / "próximo lunes" / "proximo lunes"
    - "el martes que viene" / "el próximo martes que viene" (Spanish: "next Tuesday")
    - "this friday" / "este viernes"
    - "next week" / "próxima semana"
    - "in 5 days" / "5 days from now"
    
    For "el [day] que viene" patterns, the calculation starts from the current date
    and calculates the number of days until the next occurrence of that day.
    If the day is today or has already passed this week, it returns the next week's occurrence.
    
    Args:
        date_string: Relative date expression or absolute date
        
    Returns:
        Date object or None if cannot parse
    """
    if not date_string:
        return None
    
    # Normalize the input: strip and lower
    date_string_lower = date_string.strip().lower()
    # CRITICAL: Always use the current system date as the reference point
    today = date.today()
    logger.info(f"parse_relative_date: Using current date as reference: {today} (today's weekday: {today.weekday()}, day name: {today.strftime('%A')})")
    
    # Handle common relative expressions
    # Check both normalized and original to handle encoding variations
    date_string_normalized = unicodedata.normalize('NFKD', date_string_lower)
    
    if date_string_lower in ['today', 'hoy'] or date_string_normalized in ['today', 'hoy']:
        return today
    
    # Handle "tomorrow" / "mañana" - check both original and normalized versions
    # Also handle "manana" (without tilde) in case of encoding issues
    tomorrow_variants = ['tomorrow', 'mañana', 'manana']
    if date_string_lower in tomorrow_variants or date_string_normalized in tomorrow_variants:
        tomorrow_date = today + timedelta(days=1)
        logger.info(f"parse_relative_date: Parsed '{date_string}' as tomorrow -> {tomorrow_date}")
        return tomorrow_date
    
    if date_string_lower in ['day after tomorrow', 'pasado mañana']:
        return today + timedelta(days=2)
    
    # Handle "next [day of week]"
    days_of_week = {
        'monday': 0, 'mon': 0, 'lunes': 0,
        'tuesday': 1, 'tue': 1, 'tues': 1, 'martes': 1,
        'wednesday': 2, 'wed': 2, 'miércoles': 2, 'miercoles': 2,
        'thursday': 3, 'thu': 3, 'thurs': 3, 'jueves': 3,
        'friday': 4, 'fri': 4, 'viernes': 4,
        'saturday': 5, 'sat': 5, 'sábado': 5, 'sabado': 5,
        'sunday': 6, 'sun': 6, 'domingo': 6,
    }
    
    # Check for "next [day]" pattern
    for day_name, day_num in days_of_week.items():
        if f'next {day_name}' in date_string_lower or f'próximo {day_name}' in date_string_lower or f'proximo {day_name}' in date_string_lower:
            days_ahead = day_num - today.weekday()
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7
            return today + timedelta(days=days_ahead)
        
        # Handle "el [day] que viene" pattern (Spanish: "el martes que viene" = "next Tuesday")
        # This pattern means "the [day] that comes" and always refers to the next occurrence
        # Context: fecha de comienzo es la fecha actual, luego calculamos los días hasta ese día
        if f'el {day_name} que viene' in date_string_lower or f'el próximo {day_name} que viene' in date_string_lower or f'el proximo {day_name} que viene' in date_string_lower:
            days_ahead = day_num - today.weekday()
            if days_ahead <= 0:  # Target day already happened this week (or is today)
                days_ahead += 7  # Go to next week
            result_date = today + timedelta(days=days_ahead)
            logger.info(f"parse_relative_date: Parsed '{date_string}' as 'el {day_name} que viene' -> {result_date} (today: {today}, weekday: {today.weekday()}, target weekday: {day_num}, days_ahead: {days_ahead})")
            return result_date
        
        # Also handle "this [day]" (same week)
        if f'this {day_name}' in date_string_lower or f'este {day_name}' in date_string_lower:
            days_ahead = day_num - today.weekday()
            if days_ahead < 0:  # Already passed this week
                days_ahead += 7
            return today + timedelta(days=days_ahead)
    
    # Handle "next week"
    if 'next week' in date_string_lower or 'próxima semana' in date_string_lower or 'proxima semana' in date_string_lower:
        return today + timedelta(weeks=1)
    
    # Handle "in X days"
    match = re.search(r'in\s+(\d+)\s+days?', date_string_lower)
    if match:
        days = int(match.group(1))
        return today + timedelta(days=days)
    
    # Handle "X days from now"
    match = re.search(r'(\d+)\s+days?\s+from\s+now', date_string_lower)
    if match:
        days = int(match.group(1))
        return today + timedelta(days=days)
    
    # Try to parse as absolute date using dateutil
    if dateutil_parse:
        try:
            parsed_date = dateutil_parse(date_string, fuzzy=False)
            return parsed_date.date()
        except (ValueError, TypeError):
            pass
    
    return None


def validate_future_date(date_string: Optional[str], max_days_ahead: Optional[int] = None) -> Optional[str]:
    """
    Validate and format date, ensuring it's today or in the future.
    Handles both absolute dates and relative date expressions.
    
    Args:
        date_string: Date string in various formats or relative expressions
        max_days_ahead: Maximum number of days in the future allowed (e.g., 365 for 1 year)
        
    Returns:
        Date string in YYYY-MM-DD format or None if invalid
        
    Raises:
        ValueError: If date is in the past or exceeds max_days_ahead
    """
    if not date_string:
        return None
    
    # CRITICAL: Always use current system date as reference
    today = date.today()
    logger.info(f"validate_future_date: Current system date is {today}")
    
    # First try to parse as relative date
    date_obj = parse_relative_date(date_string)
    
    if date_obj:
        # Validate it's today or future
        if date_obj < today:
            logger.warning(f"Parsed date {date_obj} from '{date_string}' is in the past (today is {today})")
            raise ValueError(f"Flight date {date_obj} is in the past. Date must be today or in the future.")
        
        # Validate max days ahead if specified
        if max_days_ahead is not None:
            days_ahead = (date_obj - today).days
            if days_ahead > max_days_ahead:
                max_date = today + timedelta(days=max_days_ahead)
                raise ValueError(
                    f"Flight date {date_obj} is more than {max_days_ahead} days in the future. "
                    f"Maximum allowed date is {max_date}."
                )
        
        formatted_date = date_obj.strftime('%Y-%m-%d')
        logger.debug(f"Parsed relative date '{date_string}' -> {formatted_date}")
        return formatted_date
    
    # Fallback to absolute date parsing
    formatted = format_date(date_string)
    if not formatted:
        return None
    
    try:
        # Parse the formatted date
        date_obj = datetime.strptime(formatted, '%Y-%m-%d').date()
        today = date.today()
        
        if date_obj < today:
            raise ValueError(f"Flight date {formatted} is in the past. Date must be today or in the future.")
        
        # Validate max days ahead if specified
        if max_days_ahead is not None:
            days_ahead = (date_obj - today).days
            if days_ahead > max_days_ahead:
                max_date = today + timedelta(days=max_days_ahead)
                raise ValueError(
                    f"Flight date {formatted} is more than {max_days_ahead} days in the future. "
                    f"Maximum allowed date is {max_date}."
                )
        
        return formatted
    except ValueError as e:
        if "is in the past" in str(e) or "more than" in str(e):
            raise
        return None

