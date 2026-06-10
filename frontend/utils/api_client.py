"""HTTP API client for the RAG Chatbot backend."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Generator, List, Optional
import requests

logger = logging.getLogger(__name__)


class APIClient:
    """Thin wrapper around the backend REST API."""

    def __init__(self, base_url: str, token: Optional[str] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.session = requests.Session()
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _raise_for_status(self, resp: requests.Response) -> None:
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            try:
                detail = resp.json().get("detail", str(exc))
            except Exception:
                detail = str(exc)
            raise RuntimeError(detail) from exc

    # ── Auth ────────

    def login(self, email: str, password: str) -> Dict[str, Any]:
        resp = self.session.post(self._url("/auth/login"), json={"email": email, "password": password})
        self._raise_for_status(resp)
        data = resp.json()
        # Update internal token
        self.token = data["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        return data

    def register(self, email: str, password: str, full_name: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"email": email, "password": password}
        if full_name:
            payload["full_name"] = full_name
        resp = self.session.post(self._url("/auth/register"), json=payload)
        self._raise_for_status(resp)
        return resp.json()

    def get_me(self) -> Dict[str, Any]:
        resp = self.session.get(self._url("/auth/me"))
        self._raise_for_status(resp)
        return resp.json()

    # ── Documents ───

    def upload_document(self, filename: str, file_bytes: bytes, content_type: str = "application/octet-stream") -> Dict[str, Any]:
        files = {"file": (filename, file_bytes, content_type)}
        resp = self.session.post(self._url("/documents/upload"), files=files)
        self._raise_for_status(resp)
        return resp.json()

    def list_documents(self, page: int = 1, page_size: int = 20, status: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status
        resp = self.session.get(self._url("/documents"), params=params)
        self._raise_for_status(resp)
        return resp.json()

    def get_document(self, document_id: str) -> Dict[str, Any]:
        resp = self.session.get(self._url(f"/documents/{document_id}"))
        self._raise_for_status(resp)
        return resp.json()

    def get_document_status(self, document_id: str) -> Dict[str, Any]:
        resp = self.session.get(self._url(f"/documents/{document_id}/status"))
        self._raise_for_status(resp)
        return resp.json()

    def delete_document(self, document_id: str) -> None:
        resp = self.session.delete(self._url(f"/documents/{document_id}"))
        self._raise_for_status(resp)

    # ── Chat ────────

    def chat_query(self, question: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"question": question}
        if session_id:
            payload["session_id"] = session_id
        resp = self.session.post(self._url("/chat/query"), json=payload)
        self._raise_for_status(resp)
        return resp.json()

    def stream_chat_query(
        self, question: str, session_id: Optional[str] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """Stream a chat query. Yields event dicts:
        - {"type": "token", "content": "..."}  — one per token
        - {"type": "done", "session_id": "...", "sources": [...]}  — final event
        """
        payload: Dict[str, Any] = {"question": question}
        if session_id:
            payload["session_id"] = session_id
        with self.session.post(
            self._url("/chat/stream"), json=payload, stream=True, timeout=120
        ) as resp:
            self._raise_for_status(resp)
            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                line = raw_line if isinstance(raw_line, str) else raw_line.decode("utf-8")
                if line.startswith("data: "):
                    try:
                        yield json.loads(line[6:])
                    except json.JSONDecodeError:
                        pass

    def create_session(self, title: str = "New Chat") -> Dict[str, Any]:
        resp = self.session.post(self._url("/chat/sessions"), json={"title": title})
        self._raise_for_status(resp)
        return resp.json()

    def list_sessions(self) -> List[Dict[str, Any]]:
        resp = self.session.get(self._url("/chat/sessions"))
        self._raise_for_status(resp)
        return resp.json()

    def get_session(self, session_id: str) -> Dict[str, Any]:
        resp = self.session.get(self._url(f"/chat/sessions/{session_id}"))
        self._raise_for_status(resp)
        return resp.json()

    def delete_session(self, session_id: str) -> None:
        resp = self.session.delete(self._url(f"/chat/sessions/{session_id}"))
        self._raise_for_status(resp)

    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        resp = self.session.get(self._url(f"/chat/sessions/{session_id}/messages"))
        self._raise_for_status(resp)
        return resp.json()

    # ── Logs ────────

    def list_logs(
        self,
        page: int = 1,
        page_size: int = 50,
        event_type: Optional[str] = None,
        level: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if event_type:
            params["event_type"] = event_type
        if level:
            params["level"] = level
        resp = self.session.get(self._url("/logs"), params=params)
        self._raise_for_status(resp)
        return resp.json()

    # ── Health ──────

    def health(self) -> Dict[str, Any]:
        resp = self.session.get(self._url("/health"))
        self._raise_for_status(resp)
        return resp.json()
