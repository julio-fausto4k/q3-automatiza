"""Merchant-specific operations and data management."""
from typing import Dict, Any, Optional
from infra.ifood_api import ifood_api
from core.auth import auth_manager
from core.cache import cache_manager
from utils.helpers import _log

class MerchantManager:
    def __init__(self):
        self.cache_ttl = 600  # 10 min

    def get_merchant_details(self, merchant_id: str) -> Optional[Dict[str, Any]]:
        key = f"merchant_details_{merchant_id}"
        hit = cache_manager.get(key)
        if hit:
            return hit
        if not auth_manager.refresh_token_if_needed():
            return None
        try:
            endpoint = f"/merchants/v1.0/merchants/{merchant_id}"
            resp = ifood_api.make_request("GET", endpoint)
            if resp:
                cache_manager.set(key, resp, ttl=self.cache_ttl)
                return resp
        except Exception as e:
            _log(f"Error fetching merchant details: {e}")
        return None

    def get_merchant_status(self, merchant_id: str) -> Optional[Dict[str, Any]]:
        key = f"merchant_status_{merchant_id}"
        hit = cache_manager.get(key)
        if hit:
            return hit
        if not auth_manager.refresh_token_if_needed():
            return None
        try:
            endpoint = f"/merchants/v1.0/merchants/{merchant_id}/status"
            resp = ifood_api.make_request("GET", endpoint)
            if resp:
                cache_manager.set(key, resp, ttl=60)
                return resp
        except Exception as e:
            _log(f"Error fetching merchant status: {e}")
        return None

    def update_merchant_status(self, merchant_id: str, status: str) -> bool:
        if not auth_manager.refresh_token_if_needed():
            return False
        try:
            endpoint = f"/merchants/v1.0/merchants/{merchant_id}/status"
            resp = ifood_api.make_request("PUT", endpoint, json={"status": status})
            if resp and not resp.get("error"):
                cache_manager.delete(f"merchant_status_{merchant_id}")
                return True
        except Exception as e:
            _log(f"Error updating merchant status: {e}")
        return False

    def get_merchant_analytics(self, merchant_id: str, period: str = "week") -> Optional[Dict[str, Any]]:
        key = f"merchant_analytics_{merchant_id}_{period}"
        hit = cache_manager.get(key)
        if hit:
            return hit
        if not auth_manager.refresh_token_if_needed():
            return None
        try:
            endpoint = f"/analytics/v1.0/merchants/{merchant_id}/summary"
            params = {"period": period}
            resp = ifood_api.make_request("GET", endpoint, params=params)
            if resp:
                cache_manager.set(key, resp, ttl=1800)  # 30 min
                return resp
        except Exception as e:
            _log(f"Error fetching merchant analytics: {e}")
        return None

merchant_manager = MerchantManager()