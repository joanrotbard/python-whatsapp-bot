"""Starlings API client for making authenticated requests."""
import logging
import requests
from typing import Optional, Dict, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config.settings import Config


logger = logging.getLogger(__name__)


class StarlingsAPIClient:
    """
    Client for interacting with Starlings Travel API.
    
    Handles authentication, token management, and API requests.
    """
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize the Starlings API client.
        
        Args:
            base_url: Base URL for Starlings API (defaults to Config value)
            api_key: API key for authentication (defaults to Config value)
        """
        self.base_url = base_url or Config.STARLINGS_API_BASE_URL
        self.api_key = api_key or Config.STARLINGS_API_KEY
        self._logger = logging.getLogger(__name__)
        
        # Create session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the Starlings API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (relative to base_url)
            headers: Optional headers dictionary
            params: Optional query parameters
            json_data: Optional JSON body
            **kwargs: Additional arguments for requests
            
        Returns:
            Response JSON as dictionary
            
        Raises:
            requests.RequestException: If request fails
        """
        # Ensure proper URL construction (handle trailing slashes)
        base_url = self.base_url.rstrip('/')
        endpoint = endpoint.lstrip('/')
        url = f"{base_url}/{endpoint}"
        headers = headers or {}
        
        # Add default headers if not already present
        if "Accept" not in headers:
            headers["Accept"] = "application/json"
        if "Content-Type" not in headers and json_data is not None:
            headers["Content-Type"] = "application/json"
        
        try:
            # Use provided timeout or default to 30 seconds
            request_timeout = timeout if timeout is not None else 30
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                timeout=request_timeout,
                **kwargs
            )
            
            # Log request details for debugging
            self._logger.debug(f"Request: {method} {url}")
            self._logger.debug(f"Headers: {headers}")
            self._logger.debug(f"Params: {params}")
            if json_data:
                import json
                try:
                    self._logger.debug(f"JSON Payload: {json.dumps(json_data, indent=2, default=str)}")
                except Exception:
                    self._logger.debug(f"JSON Payload: {json_data}")
            self._logger.debug(f"Status Code: {response.status_code}")
            
            # Check status code
            response.raise_for_status()
            
            # Check if response has content
            if not response.text:
                self._logger.error(f"Empty response from {method} {url}")
                raise requests.exceptions.RequestException(
                    f"Empty response from {url} (status {response.status_code})"
                )
            
            # Try to parse JSON
            try:
                response_data = response.json()
                return response_data
            except ValueError as json_error:
                # Response is not JSON - log the actual content
                self._logger.error(f"Non-JSON response from {method} {url}")
                self._logger.error(f"Response status: {response.status_code}")
                self._logger.error(f"Response headers: {dict(response.headers)}")
                self._logger.error(f"Response text (first 500 chars): {response.text[:500]}")
                raise requests.exceptions.RequestException(
                    f"Expected JSON response but got: {response.text[:200]}"
                ) from json_error
                
        except requests.exceptions.HTTPError as e:
            # HTTP error (4xx, 5xx)
            self._logger.error(f"HTTP error {e.response.status_code}: {method} {url}")
            if e.response is not None:
                self._logger.error(f"Response text: {e.response.text[:500]}")
                self._logger.error(f"Response headers: {dict(e.response.headers)}")
            raise
        except requests.exceptions.RequestException as e:
            # Other request errors (connection, timeout, etc.)
            self._logger.error(f"API request failed: {method} {url} - {e}")
            if hasattr(e, 'response') and e.response is not None:
                self._logger.error(f"Response text: {e.response.text[:500]}")
            raise
    
    def login(self) -> Dict[str, Any]:
        """
        Authenticate with Starlings API using API key.
        
        Returns:
            Authentication response with token, tenant, and organization
            
        Raises:
            requests.RequestException: If authentication fails
        """
        endpoint = "/login/ai"
        params = {"api_key": self.api_key}
        
        self._logger.info("Authenticating with Starlings API...")
        response = self._make_request("POST", endpoint, params=params)
        self._logger.info("Authentication successful")
        return response
    
    def refresh_token(self, phone: str, access_token: str, tenant: str) -> Dict[str, Any]:
        """
        Refresh authentication token using phone number.
        
        Args:
            phone: Phone number in format +XX-XXXXXXXXX
            access_token: Current access token
            tenant: Tenant identifier
            
        Returns:
            Response with updated access token
            
        Raises:
            requests.RequestException: If token refresh fails
        """
        endpoint = "/api/chatbot/auth/phone"
        params = {"phone": phone}
        headers = {
            "Tenant": tenant,
            "Authorization": f"Bearer {access_token}"
        }
        
        self._logger.info(f"Refreshing token for phone {phone}...")
        response = self._make_request("GET", endpoint, headers=headers, params=params)
        self._logger.info("Token refresh successful")
        return response
    
    def get_user(self, access_token: str, tenant: str) -> Dict[str, Any]:
        """
        Get user information.
        
        Args:
            access_token: Current access token
            tenant: Tenant identifier
            
        Returns:
            User information dictionary
            
        Raises:
            requests.RequestException: If request fails
        """
        endpoint = "/api/user"
        headers = {
            "Tenant": tenant,
            "Authorization": f"Bearer {access_token}"
        }
        
        self._logger.info("Fetching user information...")
        response = self._make_request("GET", endpoint, headers=headers)
        self._logger.info("User information retrieved")
        return response
    
    def get_organization(self, domain_id: str, access_token: str, tenant: str) -> Dict[str, Any]:
        """
        Get organization information by domain.
        
        Args:
            domain_id: Domain identifier
            access_token: Current access token
            tenant: Tenant identifier
            
        Returns:
            Organization information dictionary
            
        Raises:
            requests.RequestException: If request fails
        """
        endpoint = f"/api/domains/{domain_id}/organization"
        headers = {
            "Tenant": tenant,
            "Authorization": f"Bearer {access_token}"
        }
        
        self._logger.info(f"Fetching organization for domain {domain_id}...")
        response = self._make_request("GET", endpoint, headers=headers)
        self._logger.info("Organization information retrieved")
        return response
    
    def get_users(
        self,
        company_id: int,
        access_token: str,
        tenant: str,
        page: int = 1,
        per_page: int = 9999,
        with_roles: bool = False,
        only_active: bool = True
    ) -> Dict[str, Any]:
        """
        Get users for a company.
        
        Args:
            company_id: Company identifier
            access_token: Current access token
            tenant: Tenant identifier
            page: Page number (default: 1)
            per_page: Items per page (default: 9999)
            with_roles: Include roles in response (default: False)
            only_active: Only return active users (default: True)
            
        Returns:
            Users response dictionary with data array
            
        Raises:
            requests.RequestException: If request fails
        """
        endpoint = "/api/users"
        params = {
            "page": page,
            "per_page": per_page,
            "company_id": company_id,
            "with_roles": str(with_roles).lower(),
            "only_active": str(only_active).lower()
        }
        headers = {
            "Tenant": tenant,
            "Authorization": f"Bearer {access_token}"
        }
        
        self._logger.info(f"Fetching users for company {company_id}...")
        response = self._make_request("GET", endpoint, headers=headers, params=params)
        self._logger.info("Users information retrieved")
        return response
    
    def request(
        self,
        method: str,
        endpoint: str,
        access_token: str,
        tenant: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to the Starlings API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (relative to base_url)
            access_token: Access token for authentication
            tenant: Tenant identifier
            params: Optional query parameters
            json_data: Optional JSON body
            **kwargs: Additional arguments for requests
            
        Returns:
            Response JSON as dictionary
            
        Raises:
            requests.RequestException: If request fails
        """
        headers = {
            "Tenant": tenant,
            "Authorization": f"Bearer {access_token}"
        }
        return self._make_request(method, endpoint, headers=headers, params=params, json_data=json_data, **kwargs)
    
    def search_flight_availability(
        self,
        payload: Dict[str, Any],
        access_token: str,
        tenant: str
    ) -> Dict[str, Any]:
        """
        Search for flight availability.
        
        Note: This endpoint can take longer than usual, so we use a longer timeout.
        
        Args:
            payload: Flight search payload with passengers, legs, cabin_classes, feathers_passengers
            access_token: Current access token
            tenant: Tenant identifier
            
        Returns:
            Flight availability response dictionary
            
        Raises:
            requests.RequestException: If request fails
        """
        import json
        import hashlib
        
        endpoint = "/api/travel/flight/availability"
        headers = {
            "Tenant": tenant,
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # Build full URL for logging
        base_url = self.base_url.rstrip('/')
        url = f"{base_url}/{endpoint.lstrip('/')}"
        
        # Create a hash of the payload for logging/debugging
        try:
            payload_json = json.dumps(payload, indent=2, default=str, sort_keys=True)
            payload_hash = hashlib.md5(payload_json.encode()).hexdigest()[:8]
            self._logger.info(f"Starting flight availability search (payload hash: {payload_hash})")
        except Exception as e:
            self._logger.warning(f"Could not serialize payload to JSON: {e}")
            payload_hash = "unknown"
        
        # Use longer timeout for availability searches (60 seconds instead of 30)
        # This endpoint can take longer to process
        try:
            response = self._make_request(
                "POST", 
                endpoint, 
                headers=headers, 
                json_data=payload,
                timeout=60  # Longer timeout for availability searches
            )
            self._logger.info(f"Flight availability search completed successfully (payload hash: {payload_hash})")
            return response
        except requests.Timeout:
            self._logger.error(f"Flight availability search timed out after 60s (payload hash: {payload_hash})")
            raise
        except Exception as e:
            self._logger.error(f"Flight availability search failed (payload hash: {payload_hash}): {e}")
            raise

