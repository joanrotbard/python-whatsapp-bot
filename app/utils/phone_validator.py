"""Phone number validation and normalization utilities."""
import re
from typing import Tuple, Optional


class PhoneNumberValidator:
    """Utility class for phone number validation and normalization."""
    
    @staticmethod
    def normalize(phone_number: str) -> Tuple[str, str]:
        """
        Normalize phone number and prepare for API.
        
        Args:
            phone_number: Phone number in any format
            
        Returns:
            Tuple of (cleaned_digits, api_format)
            - cleaned_digits: Just the digits
            - api_format: Format with + prefix for API
        """
        # Remove spaces and dashes
        cleaned = phone_number.replace(" ", "").replace("-", "")
        
        # Extract digits
        has_plus = cleaned.startswith("+")
        digits = cleaned.replace("+", "") if has_plus else cleaned
        
        # Validate digits only
        if not digits.isdigit():
            raise ValueError(f"Invalid phone number format: {phone_number}")
        
        # Return with + prefix (as shown in Meta UI)
        api_format = f"+{digits}" if not has_plus else cleaned
        
        return digits, api_format
    
    @staticmethod
    def validate_format(phone_number: str) -> bool:
        """
        Validate phone number format.
        
        Args:
            phone_number: Phone number to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            PhoneNumberValidator.normalize(phone_number)
            return True
        except (ValueError, AttributeError):
            return False

