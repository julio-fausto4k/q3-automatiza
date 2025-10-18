"""Validation helpers for business rules."""
from typing import Dict, Any, List

def validate_catalog_item(item: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not item.get("id"):
        errors.append("id ausente")
    if not item.get("name"):
        errors.append("name ausente")
    price = item.get("price")
    if price is None or float(price) < 0:
        errors.append("price inválido")
    return errors

def validate_review_data(review: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if "rating" not in review:
        errors.append("rating ausente")
    else:
        try:
            r = float(review["rating"])
            if r < 0 or r > 5:
                errors.append("rating fora do intervalo 0..5")
        except Exception:
            errors.append("rating inválido")
    return errors
