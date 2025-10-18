"""Authentication and authorization logic."""
import time
from typing import Optional
import streamlit as st
from infra.ifood_api import ifood_api
from infra.database import db_manager
from utils.helpers import _log

class AuthManager:
    def __init__(self):
        self.token_refresh_threshold = 300  # 5 min

    def authenticate_user(self, username: str, password: str) -> bool:
        return db_manager.verify_user(username, password)

    def is_token_valid(self) -> bool:
        token = st.session_state.get("token")
        exp = st.session_state.get("token_expires_at", 0.0)
        if not token or not exp:
            return False
        return exp > (time.time() + self.token_refresh_threshold)

    def refresh_token_if_needed(self) -> bool:
        if self.is_token_valid():
            return True
        refresh_token = st.session_state.get("refresh_token")
        client_id = st.session_state.get("client_id")
        if not refresh_token or not client_id:
            _log("No refresh_token/client_id to refresh token")
            return False
        try:
            result = ifood_api.refresh_token(refresh_token, client_id)
            if result and "accessToken" in result:
                st.session_state.token = result["accessToken"]
                st.session_state.refresh_token = result.get("refreshToken", refresh_token)
                st.session_state.token_expires_at = time.time() + result.get("expiresIn", 3600)
                _log("Token refreshed successfully")
                return True
        except Exception as e:
            _log(f"Error refreshing token: {e}")
        return False

    def get_valid_token(self) -> Optional[str]:
        return st.session_state.get("token") if self.refresh_token_if_needed() else None

    def clear_session(self):
        for k in ["token","refresh_token","token_expires_at","client_id","merchant_id"]:
            if k in st.session_state:
                del st.session_state[k]

auth_manager = AuthManager()
