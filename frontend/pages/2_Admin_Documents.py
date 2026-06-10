"""Admin — Document management page."""
import os
import time
import streamlit as st
from utils.auth import init_auth_state, is_authenticated, get_token, get_current_user, clear_auth
from utils.api_client import APIClient

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Documents | RAG Chatbot", page_icon="📄", layout="wide")

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
st.title("Document Management")

# Upload section
st.subheader("Upload Document")
uploaded_file = st.file_uploader(
    "Choose a file",
    type=["pdf", "docx", "doc", "txt", "csv", "xlsx", "xls"],
    help="Supported: PDF, DOCX, TXT, CSV, XLSX (max 50 MB)",
)

if uploaded_file is not None:
    if st.button("Upload & Process", type="primary"):
        with st.spinner(f"Uploading {uploaded_file.name}…"):
            try:
                result = client().upload_document(
                    filename=uploaded_file.name,
                    file_bytes=uploaded_file.read(),
                    content_type=uploaded_file.type or "application/octet-stream",
                )
                st.success(
                    f"Uploaded '{result['filename']}' (ID: {result['id']}). "
                    "Processing started in the background."
                )
                st.rerun()
            except RuntimeError as exc:
                st.error(str(exc))

st.divider()

# Document list
st.subheader("All Documents")

col_refresh, col_filter = st.columns([1, 3])
with col_refresh:
    if st.button("Refresh"):
        st.rerun()
with col_filter:
    status_filter = st.selectbox(
        "Filter by status",
        ["All", "uploaded", "processing", "processed", "failed"],
        index=0,
    )

try:
    filter_val = None if status_filter == "All" else status_filter
    data = client().list_documents(page_size=100, status=filter_val)
    docs = data.get("documents", [])
except RuntimeError as exc:
    st.error(str(exc))
    docs = []

if not docs:
    st.info("No documents found.")
else:
    STATUS_ICONS = {
        "uploaded": "⏳",
        "processing": "🔄",
        "processed": "✅",
        "failed": "❌",
    }

    for doc in docs:
        icon = STATUS_ICONS.get(doc["processing_status"], "❓")
        with st.expander(f"{icon} {doc['filename']} — {doc['processing_status'].upper()}"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**ID:** `{doc['id']}`")
                st.markdown(f"**Type:** {doc['file_type'].upper()}")
                st.markdown(f"**Size:** {doc['file_size'] / 1024:.1f} KB")
            with col2:
                st.markdown(f"**Status:** {doc['processing_status']}")
                st.markdown(f"**Chunks:** {doc.get('num_chunks', 0)}")
                st.markdown(f"**Uploaded:** {doc['upload_date'][:19]}")

            if doc["processing_status"] == "failed" and doc.get("error_message"):
                st.error(f"Error: {doc['error_message']}")

            if st.button(f"Delete '{doc['filename']}'", key=f"del_{doc['id']}", type="secondary"):
                try:
                    client().delete_document(doc["id"])
                    st.success("Document deleted.")
                    time.sleep(0.5)
                    st.rerun()
                except RuntimeError as exc:
                    st.error(str(exc))
