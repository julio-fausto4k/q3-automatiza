# infra/ifood_api.py
"""iFood API client with authentication and request handling."""
import json
import time
from typing import Dict, Any, Optional
from urllib.parse import urljoin
from infra.http_client import http_client
from utils.constants import AUTH_URL, BASE, CATALOG_BASE
from utils.helpers import build_url, _c
import streamlit as st

class IFoodAPIClient:
    def __init__(self):
        self.base_url = BASE
        self.catalog_base = CATALOG_BASE
        self.auth_url = AUTH_URL
    
    def get_token(self, client_id: str, client_secret: str) -> Optional[Dict[str, Any]]:
        """Get OAuth token from iFood API."""
        data = {
            "grantType": "client_credentials",
            "clientId": client_id,
            "clientSecret": client_secret
        }
        
        try:
            response = http_client.post(self.auth_url, json=data)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting token: {e}")
            return None
    
    def refresh_token(self, refresh_token: str, client_id: str) -> Optional[Dict[str, Any]]:
        """Refresh OAuth token."""
        data = {
            "grantType": "refresh_token",
            "clientId": client_id,
            "refreshToken": refresh_token
        }
        
        try:
            response = http_client.post(self.auth_url, json=data)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error refreshing token: {e}")
            return None
    
    def make_request(self, method: str, endpoint: str, headers: Optional[Dict] = None, **kwargs) -> Optional[Dict]:
        """Make authenticated request to iFood API."""
        if not headers:
            headers = {}
        
        # Add authorization header if token available
        token = st.session_state.get("token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        url = build_url(endpoint)
        
        try:
            response = http_client.request(method, url, headers=headers, **kwargs)
            if response.status_code in [200, 201, 204]:
                return response.json() if response.content else {}
            elif response.status_code == 401:
                # Token expired, trigger refresh
                return {"error": "unauthorized", "status_code": 401}
            return {"error": f"HTTP {response.status_code}", "status_code": response.status_code}
        except Exception as e:
            return {"error": str(e)}
    
    def _c(self, path: str) -> str:
        """Build catalog API URL."""
        return _c(path)

# Global API client instance
ifood_api = IFoodAPIClient()