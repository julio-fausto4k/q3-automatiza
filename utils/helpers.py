"""General helper functions and utilities."""
import json
import time
import uuid
import os
from typing import Any, Optional
from urllib.parse import urljoin

def safe_json(obj: Any) -> str:
    """Safely serialize object to JSON string."""
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return str(obj) if obj is not None else "<unserializable>"

def cache_bust(url: str | None) -> str | None:
    """Add cache busting parameter to URL."""
    if not url:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}cb={int(time.time())}"

def _is_uuid(val: str) -> bool:
    """Check if string is a valid UUID."""
    try:
        uuid.UUID(str(val).strip())
        return True
    except Exception:
        return False

def build_url(base: str, path: str) -> str:
    """Build absolute URL respecting slashes without duplication."""
    base_with_slash = base + "/" if not base.endswith("/") else base
    return urljoin(base_with_slash, path.lstrip("/"))

def _c(path: str) -> str:
    """Build safe URL for Catalog v2 API."""
    from .constants import CATALOG_BASE
    base = CATALOG_BASE if CATALOG_BASE.endswith("/") else CATALOG_BASE + "/"
    return urljoin(base, path.lstrip("/"))

def _img_url_from_path(path: str | None) -> str | None:
    """Convert image path to full URL."""
    if not path:
        return None
    s = str(path)
    # Already a full URL
    if s.startswith("http"):
        return s
    # iFood CDN public classic path
    if s.startswith("image/upload") or s.startswith("/image/upload"):
        return f"https://static-images.ifood.com.br/{s.lstrip('/')}"
    # Fallback: static catalog base
    base = os.getenv("CATALOG_STATIC_BASE") or "https://merchant-api.ifood.com.br/catalog/static"
    return f"{base.rstrip('/')}/{s.lstrip('/')}"
