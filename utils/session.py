"""Session state management utilities."""
import streamlit as st
from typing import Any, List
from .constants import SESSION_KEYS_TO_CLEAR

def force_logout_and_clear_all():
    """Clear ALL session data and cache."""
    # Clear session_state keys
    for key in SESSION_KEYS_TO_CLEAR:
        if key in st.session_state:
            del st.session_state[key]
    
    # Clear additional session state overrides
    for key in ["_status_override", "_image_override", "_meta_override"]:
        if key in st.session_state:
            del st.session_state[key]
    
    # Clear Streamlit caches
    try:
        st.cache_data.clear()
    except:
        pass
    
    try:
        st.cache_resource.clear() 
    except:
        pass

def reset_all_caches():
    """Reset caches and session cache-related data."""
    try:
        st.cache_data.clear()
    except Exception:
        pass
    
    # Clear cache-related session data
    cache_keys = ["_options_index", "_product_img_index", "_groups_to_draw"]
    for k in cache_keys:
        st.session_state.pop(k, None)
    
    # Bump cache version for argument-based invalidation
    st.session_state["_cache_bump"] = st.session_state.get("_cache_bump", 0) + 1

def init_session_defaults():
    """Initialize session state with default values."""
    from .constants import SESSION_DEFAULTS, ADDITIONAL_SESSION_KEYS
    
    # Set main defaults
    for k, v in SESSION_DEFAULTS.items():
        st.session_state.setdefault(k, v)
    
    # Set additional defaults
    for k, v in ADDITIONAL_SESSION_KEYS.items():
        st.session_state.setdefault(k, v)
    
    # Initialize override dictionaries
    st.session_state.setdefault("_status_override", {})
    st.session_state.setdefault("_image_override", {})
    st.session_state.setdefault("_meta_override", {})

def get_session_value(key: str, default: Any = None) -> Any:
    """Safely get session state value with fallback."""
    return st.session_state.get(key, default)

def set_session_value(key: str, value: Any):
    """Set session state value."""
    st.session_state[key] = value

def clear_session_keys(keys: List[str]):
    """Clear specific session state keys."""
    for key in keys:
        if key in st.session_state:
            del st.session_state[key]
