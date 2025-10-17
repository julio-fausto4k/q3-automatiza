"""Validation utilities and functions."""
import re
from typing import Any, Dict, List, Optional

def _env_set(name: str, default_csv: str) -> set[str]:
    """Get environment variable as set of uppercase strings."""
    import os
    try:
        raw = os.getenv(name, default_csv)
        return {x.strip().upper() for x in str(raw).split(",") if x.strip()}
    except Exception:
        return set()

def _env_int(name: str, default: int) -> int:
    """Get environment variable as integer with fallback."""
    import os
    try:
        v = int(str(os.getenv(name, "")).strip())
        return v if v > 0 else default
    except Exception:
        return default

def _env_float(name: str, default: float) -> float:
    """Get environment variable as float with fallback."""
    import os
    try:
        v = float(str(os.getenv(name, "")).strip().replace(",", "."))
        return v if v > 0 else default
    except Exception:
        return default

def _flag(env_name: str, default: bool = False) -> bool:
    """Parse environment variable as boolean flag."""
    import os
    v = str(os.getenv(env_name, "1" if default else "0")).strip().lower()
    return v in ("1", "true", "t", "yes", "y", "sim", "on")

def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_required_fields(data: Dict[str, Any], required: List[str]) -> List[str]:
    """Validate that required fields are present and non-empty."""
    missing = []
    for field in required:
        if field not in data or not data[field]:
            missing.append(field)
    return missing
