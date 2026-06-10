"""Admin — System logs viewer."""
import os
import streamlit as st
import pandas as pd
from utils.auth import init_auth_state, is_authenticated, get_token, get_current_user, clear_auth
from utils.api_client import APIClient

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Logs | RAG Chatbot", page_icon="📋", layout="wide")

init_auth_state()

if not is_authenticated():
    st.warning("Please log in.")
    st.stop()

user = get_current_user()
if user.get("role") != "admin":
    st.error("Admin access required to view this page.")
    st.stop()


def client() -> APIClient:
    return APIClient(BACKEND_URL, token=get_token())


# ── Sidebar ─────────
with st.sidebar:
    st.markdown(f"**{user.get('full_name') or user.get('email', '')}** (admin)")
    if st.button("Logout", use_container_width=True):
        clear_auth()
        st.rerun()

# ── Main ────────────
st.title("System Logs")

# Filters
col1, col2, col3 = st.columns(3)
with col1:
    level_filter = st.selectbox("Level", ["All", "info", "warning", "error"], index=0)
with col2:
    event_type_filter = st.text_input("Event type (exact)", placeholder="e.g. login_success")
with col3:
    page_size = st.selectbox("Rows per page", [25, 50, 100, 200], index=1)

if st.button("Refresh", type="primary"):
    st.rerun()

# Pagination state
if "log_page" not in st.session_state:
    st.session_state["log_page"] = 1

try:
    data = client().list_logs(
        page=st.session_state["log_page"],
        page_size=page_size,
        event_type=event_type_filter or None,
        level=None if level_filter == "All" else level_filter,
    )
    logs = data.get("logs", [])
    total = data.get("total", 0)
except RuntimeError as exc:
    st.error(str(exc))
    logs = []
    total = 0

st.caption(f"Total records: {total}")

if logs:
    df = pd.DataFrame(logs)
    # Reorder / rename columns for display
    display_cols = ["created_at", "level", "event_type", "message", "user_id"]
    display_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(
        df[display_cols].rename(
            columns={
                "created_at": "Timestamp",
                "level": "Level",
                "event_type": "Event",
                "message": "Message",
                "user_id": "User ID",
            }
        ),
        use_container_width=True,
        height=600,
    )

    # Pagination controls
    total_pages = max(1, -(-total // page_size))  # ceiling division
    col_prev, col_page, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("Previous", disabled=st.session_state["log_page"] <= 1):
            st.session_state["log_page"] -= 1
            st.rerun()
    with col_page:
        st.markdown(
            f"<div style='text-align:center'>Page {st.session_state['log_page']} / {total_pages}</div>",
            unsafe_allow_html=True,
        )
    with col_next:
        if st.button("Next", disabled=st.session_state["log_page"] >= total_pages):
            st.session_state["log_page"] += 1
            st.rerun()
else:
    st.info("No log entries found for the selected filters.")
