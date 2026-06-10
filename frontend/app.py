"""Chatbot — Login / landing page."""
import os
import streamlit as st
from utils.auth import init_auth_state, is_authenticated, set_auth, get_current_user
from utils.api_client import APIClient

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Chatbot",
    page_icon="💬",
    layout="centered",
    initial_sidebar_state="collapsed",
)

init_auth_state()


def _client() -> APIClient:
    return APIClient(BACKEND_URL)


def render_login_form() -> None:
    st.title("Chatbot")
    st.markdown("Sign in to access the RAG-powered chatbot.")

    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="you@example.com")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)

        if submitted:
            if not email or not password:
                st.error("Please enter both email and password.")
            else:
                with st.spinner("Signing in…"):
                    try:
                        data = _client().login(email, password)
                        set_auth(data["access_token"], data["user"])
                        st.success("Logged in successfully!")
                        st.rerun()
                    except RuntimeError as exc:
                        st.error(str(exc))

    with tab_register:
        with st.form("register_form"):
            reg_name = st.text_input("Full Name", placeholder="Jane Doe")
            reg_email = st.text_input("Email", placeholder="you@example.com", key="reg_email")
            reg_password = st.text_input("Password (min 8 chars)", type="password", key="reg_pw")
            reg_confirm = st.text_input("Confirm Password", type="password", key="reg_pw2")
            reg_submitted = st.form_submit_button("Create Account", use_container_width=True)

        if reg_submitted:
            if not reg_email or not reg_password:
                st.error("Email and password are required.")
            elif reg_password != reg_confirm:
                st.error("Passwords do not match.")
            elif len(reg_password) < 8:
                st.error("Password must be at least 8 characters.")
            else:
                with st.spinner("Creating account…"):
                    try:
                        _client().register(reg_email, reg_password, reg_name or None)
                        st.success("Account created! Please sign in.")
                    except RuntimeError as exc:
                        st.error(str(exc))


def render_home() -> None:
    user = get_current_user()
    st.title(f"Welcome, {user.get('full_name') or user.get('email', 'User')}!")
    st.markdown(
        """
        Use the navigation sidebar to:
        - **Chat** — ask questions about your uploaded documents
        - **Admin: Documents** *(admin only)* — upload and manage documents
        - **Admin: Logs** *(admin only)* — view system activity logs
        """
    )
    st.info("Select a page from the sidebar to get started.")


if is_authenticated():
    render_home()
else:
    render_login_form()
