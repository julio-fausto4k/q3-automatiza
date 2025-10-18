"""Constants and configuration values used throughout the application."""
import os

# API Base URLs
CATALOG_BASE = os.getenv(
    "IF_CATALOG_BASE",
    "https://merchant-api.ifood.com.br/catalog/v2.0/",
).rstrip("/")

IF_BASE = os.getenv(
    "IF_BASE", 
    "https://merchant-api.ifood.com.br/",
).rstrip("/")

BASE = "https://merchant-api.ifood.com.br"
AUTH_URL = f"{BASE}/authentication/v1.0/oauth/token"

# Database paths
DB_PATH_REVIEWS = "reviews.db"
DB_PATH_USERS = "users.db"

# Session state defaults
SESSION_DEFAULTS = {
    "api_connected": False,
    "logged_in": False,
    "logged_user": "",
    "token": "",
    "refresh_token": "",
    "token_expires_at": 0.0,
    "client_id": os.getenv("CLIENT_ID") or "",
    "client_secret": os.getenv("CLIENT_SECRET") or "",
}

# Additional session state keys
ADDITIONAL_SESSION_KEYS = {
    "_access_token": None,
    "merchant_id": None,
    "store_id": None,
    "_reply_open": False,
    "_selected_review": None,
    "_reply_text": "",
    "_reviews_last_refresh": 0.0,
}

# Keys to clear during logout
SESSION_KEYS_TO_CLEAR = [
    "token", "refresh_token", "token_expires_at", "api_connected",
    "logged_in", "logged_user", "merchant_id", "store_id", 
    "client_id", "client_secret", "_access_token",
    "catalog_id", "catalog_context", "catalog_loaded",
    "_product_img_index", "_options_index", "_groups_to_draw",
    "favorites", "merchants_cache"
]
