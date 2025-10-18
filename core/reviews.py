"""Review management and AI-powered responses."""
from typing import List, Dict, Any, Optional
from infra.ifood_api import ifood_api
from infra.openai_client import openai_client
from infra.database import db_manager
from infra.email import email_service
from core.auth import auth_manager
from core.cache import cache_manager
from utils.helpers import _log

class ReviewManager:
    def __init__(self):
        self.cache_ttl = 180  # 3 min

    def _fetch_reviews_from_api(self, merchant_id: str, limit: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
        if not auth_manager.refresh_token_if_needed():
            return None
        try:
            endpoint = f"/review/v1.0/merchants/{merchant_id}/reviews"
            params = {"limit": limit} if limit else None
            resp = ifood_api.make_request("GET", endpoint, params=params)
            if resp and isinstance(resp, dict) and "reviews" in resp:
                return resp["reviews"]
        except Exception as e:
            _log(f"Error fetching reviews from API: {e}")
        return None

    def get_reviews(self, merchant_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        cache_key = f"reviews_{merchant_id}_{limit or 'all'}"
        hit = cache_manager.get(cache_key)
        if hit:
            return hit
        api_rows = self._fetch_reviews_from_api(merchant_id, limit)
        if api_rows:
            db_manager.upsert_reviews(merchant_id, api_rows)
            cache_manager.set(cache_key, api_rows, ttl=self.cache_ttl)
            return api_rows
        db_rows = db_manager.get_reviews(merchant_id, limit)
        if db_rows:
            cache_manager.set(cache_key, db_rows, ttl=self.cache_ttl)
        return db_rows or []

    def generate_ai_reply(self, review: Dict[str, Any], context: str = "") -> Optional[str]:
        text = review.get("comment", "")
        rating = review.get("rating", 0)
        if not text:
            return None
        try:
            return openai_client.generate_review_reply(text, rating, context)
        except Exception as e:
            _log(f"Error generating AI reply: {e}")
            return None

    def submit_reply(self, merchant_id: str, review_id: str, reply_text: str) -> bool:
        if not auth_manager.refresh_token_if_needed():
            return False
        try:
            endpoint = f"/review/v1.0/merchants/{merchant_id}/reviews/{review_id}/reply"
            resp = ifood_api.make_request("POST", endpoint, json={"reply": reply_text})
            if resp and not resp.get("error"):
                db_manager.save_reply_to_db(review_id, reply_text)
                cache_manager.invalidate_pattern(f"reviews_{merchant_id}")
                return True
        except Exception as e:
            _log(f"Error submitting reply: {e}")
        return False

    def send_review_notification(self, to_email: str, review: Dict[str, Any], merchant_name: str) -> bool:
        try:
            rating = review.get("rating", 0)
            comment = review.get("comment", "")
            customer_name = review.get("customer_name", "Cliente")
            subject = f"Nova avaliação ({rating}⭐) - {merchant_name}"
            msg = (
                f"Nova avaliação recebida para {merchant_name}:\n\n"
                f"Cliente: {customer_name}\n"
                f"Avaliação: {rating}/5 ⭐\n"
                f"Comentário: {comment}\n\n"
                "Acesse o sistema para responder."
            )
            return email_service.send_notification(to_email, subject, msg)
        except Exception as e:
            _log(f"Error sending review notification: {e}")
            return False

review_manager = ReviewManager()
