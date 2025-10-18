"""Catalog management and operations."""
from typing import List, Dict, Any, Optional, Tuple
from infra.ifood_api import ifood_api
from core.auth import auth_manager
from core.cache import cache_manager
from utils.helpers import _log

class CatalogManager:
    def __init__(self):
        self.cache_ttl = 300  # 5 min

    def get_merchants(self) -> Optional[List[Dict[str, Any]]]:
        cache_key = "merchants"
        hit = cache_manager.get(cache_key)
        if hit:
            return hit
        if not auth_manager.refresh_token_if_needed():
            return None
        try:
            resp = ifood_api.make_request("GET", "/merchants/v1.0/merchants")
            if isinstance(resp, list):
                cache_manager.set(cache_key, resp, ttl=self.cache_ttl)
                return resp
        except Exception as e:
            _log(f"Error fetching merchants: {e}")
        return None

    def get_catalog(self, merchant_id: str) -> Optional[Dict[str, Any]]:
        cache_key = f"catalog_{merchant_id}"
        hit = cache_manager.get(cache_key)
        if hit:
            return hit
        if not auth_manager.refresh_token_if_needed():
            return None
        try:
            endpoint = f"/catalog/v1.0/merchants/{merchant_id}/catalog"
            resp = ifood_api.make_request("GET", endpoint)
            if resp and isinstance(resp, dict) and "categories" in resp:
                cache_manager.set(cache_key, resp, ttl=self.cache_ttl)
                return resp
        except Exception as e:
            _log(f"Error fetching catalog for {merchant_id}: {e}")
        return None

    def get_item_details(self, merchant_id: str, item_id: str) -> Optional[Dict[str, Any]]:
        cache_key = f"item_{merchant_id}_{item_id}"
        hit = cache_manager.get(cache_key)
        if hit:
            return hit
        if not auth_manager.refresh_token_if_needed():
            return None
        try:
            endpoint = f"/catalog/v1.0/merchants/{merchant_id}/items/{item_id}"
            resp = ifood_api.make_request("GET", endpoint)
            if resp:
                cache_manager.set(cache_key, resp, ttl=self.cache_ttl)
                return resp
        except Exception as e:
            _log(f"Error fetching item {item_id} for {merchant_id}: {e}")
        return None

    def update_item_status(self, merchant_id: str, item_id: str, available: bool) -> bool:
        if not auth_manager.refresh_token_if_needed():
            return False
        try:
            endpoint = f"/catalog/v1.0/merchants/{merchant_id}/items/{item_id}/status"
            data = {"available": available}
            resp = ifood_api.make_request("PUT", endpoint, json=data)
            if resp and not resp.get("error"):
                cache_manager.invalidate_pattern(f"catalog_{merchant_id}")
                cache_manager.invalidate_pattern(f"item_{merchant_id}_{item_id}")
                return True
        except Exception as e:
            _log(f"Error updating item status: {e}")
        return False

    def bulk_update_items(self, merchant_id: str, updates: List[Dict[str, Any]]) -> Tuple[int, int]:
        ok = 0
        for u in updates:
            iid = u.get("item_id")
            av = u.get("available")
            if iid is not None and av is not None:
                if self.update_item_status(merchant_id, iid, av):
                    ok += 1
        return ok, len(updates)

catalog_manager = CatalogManager()
