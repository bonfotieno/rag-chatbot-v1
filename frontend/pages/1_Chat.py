"""Chat page — RAG-powered Q&A interface."""
import os
import streamlit as st
from utils.auth import init_auth_state, is_authenticated, get_token, get_current_user, clear_auth
from utils.api_client import APIClient

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Chat | RAG Chatbot", page_icon="💬", layout="wide")

init_auth_state()

if not is_authenticated():
    st.warning("Please log in to use the chat.")
    st.stop()


def client() -> APIClient:
    return APIClient(BACKEND_URL, token=get_token())


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    user = get_current_user()
    st.markdown(f"**{user.get('full_name') or user.get('email', '')}**")
    st.caption(f"Role: {user.get('role', '')}")

    if st.button("Logout", use_container_width=True):
        clear_auth()
        st.rerun()

    st.divider()
    st.subheader("Sessions")

    if st.button("+ New Chat", use_container_width=True):
        st.session_state.pop("active_session_id", None)
        st.session_state.pop("messages", None)
        st.rerun()

    try:
        sessions = client().list_sessions()
    except RuntimeError:
        sessions = []

    for sess in sessions:
        label = sess.get("title") or "Untitled"
        sess_id = sess["id"]
        is_active = st.session_state.get("active_session_id") == sess_id
        btn_label = f"{'► ' if is_active else ''}{label[:40]}"
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(btn_label, key=f"sess_{sess_id}", use_container_width=True):
                st.session_state["active_session_id"] = sess_id
                # Load messages
                try:
                    msgs = client().get_messages(sess_id)
                    st.session_state["messages"] = [
                        {"role": m["role"], "content": m["content"], "sources": m.get("sources")}
                        for m in msgs
                    ]
                except RuntimeError:
                    st.session_state["messages"] = []
                st.rerun()
        with col2:
            if st.button("🗑", key=f"del_{sess_id}"):
                try:
                    client().delete_session(sess_id)
                    if st.session_state.get("active_session_id") == sess_id:
                        st.session_state.pop("active_session_id", None)
                        st.session_state.pop("messages", None)
                except RuntimeError as e:
                    st.error(str(e))
                st.rerun()

# ── Main chat area ────────────────────────────────────────────────────────────
st.title("Chat")

if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Render history
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander("Sources"):
                for src in msg["sources"]:
                    st.markdown(
                        f"- **{src.get('filename', 'Unknown')}** "
                        f"(chunk {src.get('chunk_index', '?')}, "
                        f"page {src.get('page_number', 'N/A')}, "
                        f"score: {src.get('score', 0):.3f})"
                    )

# Input
if question := st.chat_input("Ask a question about your documents…"):
    # Show user message immediately
    st.session_state["messages"].append({"role": "user", "content": question, "sources": None})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        try:
            _state = {"sources": [], "session_id": None}

            def token_stream():
                for event in client().stream_chat_query(
                    question=question,
                    session_id=st.session_state.get("active_session_id"),
                ):
                    if event["type"] == "token":
                        yield event["content"]
                    elif event["type"] == "done":
                        _state["sources"] = event.get("sources") or []
                        _state["session_id"] = event.get("session_id")

            answer = st.write_stream(token_stream())

            if _state["session_id"]:
                st.session_state["active_session_id"] = _state["session_id"]

            final_sources = _state["sources"]
            if final_sources:
                with st.expander("Sources"):
                    for src in final_sources:
                        st.markdown(
                            f"- **{src.get('filename', 'Unknown')}** "
                            f"(chunk {src.get('chunk_index', '?')}, "
                            f"page {src.get('page_number', 'N/A')}, "
                            f"score: {src.get('score', 0):.3f})"
                        )

            st.session_state["messages"].append(
                {"role": "assistant", "content": answer, "sources": _state["sources"]}
            )

        except RuntimeError as exc:
            error_msg = f"Error: {exc}"
            st.error(error_msg)
            st.session_state["messages"].append(
                {"role": "assistant", "content": error_msg, "sources": None}
            )
