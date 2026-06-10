"""Session-state authentication helpers for Streamlit."""
from __future__ import annotations

from typing import Any, Dict, Optional
import streamlit as st


_TOKEN_KEY = "_auth_token"
_USER_KEY = "_auth_user"


def init_auth_state() -> None:
    """Initialise authentication keys in session_state if absent."""
    if _TOKEN_KEY not in st.session_state:
        st.session_state[_TOKEN_KEY] = None
    if _USER_KEY not in st.session_state:
        st.session_state[_USER_KEY] = None


def is_authenticated() -> bool:
    """Return True if a valid token is stored in session_state."""
    init_auth_state()
    return st.session_state[_TOKEN_KEY] is not None


def get_token() -> Optional[str]:
    """Return the current JWT token or None."""
    init_auth_state()
    return st.session_state[_TOKEN_KEY]


def get_current_user() -> Optional[Dict[str, Any]]:
    """Return the current user dict or None."""
    init_auth_state()
    return st.session_state[_USER_KEY]


def set_auth(token: str, user: Dict[str, Any]) -> None:
    """Store a token and user profile in session_state."""
    st.session_state[_TOKEN_KEY] = token
    st.session_state[_USER_KEY] = user


def clear_auth() -> None:
    """Remove authentication data from session_state (logout)."""
    st.session_state[_TOKEN_KEY] = None
    st.session_state[_USER_KEY] = None
