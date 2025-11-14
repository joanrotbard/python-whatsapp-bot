"""Authentication service for Starlings API."""
import json
import logging
from typing import Dict, Any, Optional

from app.infrastructure.clients.starlings_api_client import StarlingsAPIClient
from app.domain.interfaces.session_storage import ISessionStorage
from app.infrastructure.repositories.session_storage import RedisSessionStorage
from app.config.settings import Config


logger = logging.getLogger(__name__)


class AuthenticationService:
    """
    Service for handling Starlings API authentication flow.
    
    Orchestrates the complete authentication process:
    1. Initial login with API key
    2. Token refresh with phone number
    3. Fetch user information
    4. Fetch organization information
    5. Store all data in session
    """
    
    def __init__(
        self,
        api_client: Optional[StarlingsAPIClient] = None,
        session_storage: Optional[ISessionStorage] = None
    ):
        """
        Initialize authentication service.
        
        Args:
            api_client: Starlings API client instance (Dependency Injection)
            session_storage: Session storage instance (Dependency Injection)
        """
        self.api_client = api_client or StarlingsAPIClient()
        self.session_storage = session_storage or RedisSessionStorage()
        self._logger = logging.getLogger(__name__)
        self._session_id = "default"  # Single global session for now
    
    def authenticate(self, phone_number: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the complete authentication flow.
        
        Args:
            phone_number: Phone number for token refresh (defaults to Config value)
            
        Returns:
            Complete session data dictionary
            
        Raises:
            Exception: If any step of authentication fails
        """
        phone_number = phone_number or Config.STARLINGS_PHONE_NUMBER
        
        if not phone_number:
            raise ValueError("Phone number is required for authentication")
        
        self._logger.info("Starting authentication flow...")
        
        try:
            # Step 1: Initial login with API key
            self._logger.info("Step 1: Logging in with API key...")
            login_response = self.api_client.login()
            
            access_token = login_response.get("token")
            tenant = login_response.get("tenant")
            organization = login_response.get("organization")
            
            if not access_token or not tenant:
                raise ValueError("Invalid login response: missing token or tenant")
            
            self._logger.info(f"Login successful - Token: {access_token[:20]}..., Tenant: {tenant[:20]}...")
            
            # Step 2: Refresh token with phone number
            self._logger.info("Step 2: Refreshing token with phone number...")
            refresh_response = self.api_client.refresh_token(phone_number, access_token, tenant)
            
            # Update access token from refresh response
            # Try multiple possible field names for the token
            new_access_token = (
                refresh_response.get("token") or 
                refresh_response.get("access_token") or 
                access_token
            )
            if new_access_token != access_token:
                access_token = new_access_token
                self._logger.info("Token refreshed successfully")
            else:
                self._logger.info("Token refresh completed (using existing token)")
            
            # Step 3: Get user information
            self._logger.info("Step 3: Fetching user information...")
            user_response = self.api_client.get_user(access_token, tenant)
            
            # Step 4: Get organization information
            # Extract domain ID from organization
            domain_id = None
            if organization and organization.get("domains") and len(organization["domains"]) > 0:
                domain_id = organization["domains"][0].get("id")
            
            if not domain_id:
                self._logger.warning("No domain ID found in organization, skipping organization fetch")
                organization_data = organization
            else:
                self._logger.info(f"Step 4: Fetching organization for domain {domain_id}...")
                organization_data = self.api_client.get_organization(domain_id, access_token, tenant)
            
            # Step 5: Build initial session data
            session_data = {
                "access_token": access_token,
                "tenant": tenant,
                "organization": organization_data,
                "user": user_response,
                "buyer": organization_data.get("buyer") if isinstance(organization_data, dict) else None,
                "authenticated_at": self._get_timestamp(),
            }
            
            # Step 6: Set organization_type and handle users based on role
            session_data["organization_type"] = "company"
            
            highest_role = user_response.get("highestRole", "")
            self._logger.info(f"User highest role: {highest_role}")
            
            if highest_role == "basic-user":
                # For basic users, only include themselves
                session_data["users"] = json.dumps([user_response])
                session_data["feathers_passengers"] = json.dumps([{
                    "user_id": user_response.get("id"),
                    "cost_center_id": None
                }])
                self._logger.info("Basic user detected - set users and feathers_passengers to current user only")
            else:
                # For other roles, fetch all company users
                organization_id = None
                if isinstance(organization_data, dict):
                    organization_id = organization_data.get("id")
                
                if organization_id:
                    self._logger.info(f"Step 6: Fetching users for company {organization_id}...")
                    users_response = self.api_client.get_users(
                        company_id=organization_id,
                        access_token=access_token,
                        tenant=tenant,
                        page=1,
                        per_page=9999,
                        with_roles=False,
                        only_active=True
                    )
                    # Store the data array from response
                    session_data["users"] = users_response.get("data", [])
                    self._logger.info(f"Retrieved {len(session_data['users'])} users for company")
                else:
                    self._logger.warning("No organization ID found - cannot fetch users")
                    session_data["users"] = []
            
            # Add cost centers from user data
            cost_centers = user_response.get("cost_centers", [])
            session_data["cost_centers"] = cost_centers
            self._logger.info(f"Added {len(cost_centers)} cost centers to session")
            
            # Store session
            self.session_storage.set_session(self._session_id, session_data)
            self._logger.info("Authentication flow completed successfully")
            self._logger.info(f"Session stored with ID: {self._session_id}")
            
            return session_data
            
        except Exception as e:
            self._logger.error(f"Authentication failed: {e}", exc_info=True)
            raise
    
    def get_session(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve current session data.
        
        Returns:
            Session data dictionary or None if not authenticated
        """
        return self.session_storage.get_session(self._session_id)
    
    def is_authenticated(self) -> bool:
        """
        Check if session is authenticated.
        
        Returns:
            True if authenticated, False otherwise
        """
        session = self.get_session()
        return session is not None and session.get("access_token") is not None
    
    def get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for API requests.
        
        Returns:
            Dictionary with Tenant and Authorization headers
            
        Raises:
            ValueError: If not authenticated
        """
        session = self.get_session()
        if not session:
            raise ValueError("Not authenticated. Please run authentication flow first.")
        
        return {
            "Tenant": session["tenant"],
            "Authorization": f"Bearer {session['access_token']}"
        }
    
    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp as ISO string."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"

