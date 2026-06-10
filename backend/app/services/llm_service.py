"""LLM service using litellm to abstract over Anthropic/OpenAI/Ollama."""
import logging
from typing import List, Dict, Any, Optional
import litellm
from ..config import settings

logger = logging.getLogger(__name__)

# litellm uses provider-prefixed model strings when provider != openai
_PROVIDER_PREFIX_MAP = {
    "anthropic": "anthropic/",
    "openai": "",
    "ollama": "ollama/",
}


class LLMService:
    """Thin wrapper around litellm.completion for multi-provider LLM calls."""

    def __init__(self) -> None:
        self.provider = settings.LLM_PROVIDER
        self.model = settings.LLM_MODEL
        self._configure_provider()

    def _configure_provider(self) -> None:
        if self.provider == "anthropic":
            litellm.anthropic_key = settings.ANTHROPIC_API_KEY
        elif self.provider == "openai":
            litellm.openai_key = settings.OPENAI_API_KEY

    def _full_model_name(self) -> str:
        prefix = _PROVIDER_PREFIX_MAP.get(self.provider, "")
        return f"{prefix}{self.model}"

    def complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Send a chat completion request and return the assistant text response.

        Args:
            messages: List of {"role": "user"|"assistant", "content": "..."} dicts.
            system: Optional system prompt prepended to the conversation.
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature (0.0 = deterministic).

        Returns:
            The assistant's response as a plain string.
        """
        full_messages: List[Dict[str, str]] = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        model_name = self._full_model_name()
        logger.info("LLM call: model=%s messages=%d", model_name, len(full_messages))

        kwargs: Dict[str, Any] = {
            "model": model_name,
            "messages": full_messages,
            "max_tokens": max_tokens,
        }
        if self.provider == "ollama":
            kwargs["api_base"] = settings.OLLAMA_BASE_URL
        if self.provider != "anthropic":
            kwargs["temperature"] = temperature

        response = litellm.completion(**kwargs)

        content = response.choices[0].message.content
        return content or ""

    def complete_with_context(
        self,
        question: str,
        context_chunks: List[str],
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Generate an answer grounded in retrieved context chunks.

        Args:
            question: The user's question.
            context_chunks: Relevant text chunks retrieved from the vector store.
            chat_history: Prior conversation turns for multi-turn support.

        Returns:
            The grounded assistant answer as a string.
        """
        context = "\n\n---\n\n".join(context_chunks)
        system_prompt = (
            "You are a helpful assistant. Answer the user's question directly and naturally, "
            "as if you already know the answer — do NOT say 'based on the context', "
            "'according to the document', 'the context says', or any similar phrase. "
            "Just answer.\n\n"
            "Rules:\n"
            "- Use ONLY the information in the context below to form your answer.\n"
            "- If the question cannot be answered from the context, reply: \"I don't know.\"\n"
            "- Do NOT hallucinate or invent information.\n"
            "- Be clear, concise, and definitive.\n\n"
            f"Context:\n{context}"
        )

        messages: List[Dict[str, str]] = list(chat_history or [])
        messages.append({"role": "user", "content": question})

        return self.complete(messages=messages, system=system_prompt)

    def stream_with_context(
        self,
        question: str,
        context_chunks: List[str],
        chat_history: Optional[List[Dict[str, str]]] = None,
    ):
        """Stream a grounded answer token by token."""
        context = "\n\n---\n\n".join(context_chunks)
        system_prompt = (
            "You are a helpful assistant. Answer the user's question directly and naturally, "
            "as if you already know the answer — do NOT say 'based on the context', "
            "'according to the document', 'the context says', or any similar phrase. "
            "Just answer.\n\n"
            "Rules:\n"
            "- Use ONLY the information in the context below to form your answer.\n"
            "- If the question cannot be answered from the context, reply: \"I don't know.\"\n"
            "- Do NOT hallucinate or invent information.\n"
            "- Be clear, concise, and definitive.\n\n"
            f"Context:\n{context}"
        )

        full_messages: List[Dict[str, str]] = []
        full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(list(chat_history or []))
        full_messages.append({"role": "user", "content": question})

        model_name = self._full_model_name()
        kwargs: Dict[str, Any] = {
            "model": model_name,
            "messages": full_messages,
            "max_tokens": 2048,
            "stream": True,
        }
        if self.provider == "ollama":
            kwargs["api_base"] = settings.OLLAMA_BASE_URL
        if self.provider != "anthropic":
            kwargs["temperature"] = 0.7

        response = litellm.completion(**kwargs)
        for chunk in response:
            token = chunk.choices[0].delta.content
            if token:
                yield token


# Module-level singleton
llm_service = LLMService()
