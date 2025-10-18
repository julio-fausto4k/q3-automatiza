"""Text formatting and display utilities."""
import re
from typing import Any

def format_currency(value: float) -> str:
    """Format value as Brazilian currency."""
    return f"R$ {value:.2f}".replace(".", ",")

def format_percentage(value: float) -> str:
    """Format value as percentage."""
    return f"{value:.1f}%"

def sanitize_text(text: str) -> str:
    """Sanitize text for safe display."""
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to maximum length with ellipsis."""
    if not text or len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."
