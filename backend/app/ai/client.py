"""Async LLM client wrapper for MiniMax M2.5 via OpenAI-compatible API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError

from app.config import settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class LLMError(Exception):
    """Base exception for LLM client errors."""


class LLMNotConfiguredError(LLMError):
    """Raised when the API key is not set."""


class LLMAPIError(LLMError):
    """Raised when the LLM API returns an error."""


@dataclass
class LLMResponse:
    """Response from an LLM completion."""

    content: str
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str = ""


@dataclass
class LLMMessage:
    """A single message in a conversation."""

    role: str  # "system", "user", or "assistant"
    content: str


def _to_api_messages(messages: list[LLMMessage]) -> list[dict[str, Any]]:
    """Convert LLMMessages to the dict format expected by the OpenAI SDK."""
    return [{"role": m.role, "content": m.content} for m in messages]


@dataclass
class LLMClient:
    """Async wrapper around MiniMax M2.5 via OpenAI-compatible API.

    Reads configuration from app settings. Raises LLMNotConfiguredError
    if the API key is not set.
    """

    model: str = field(default_factory=lambda: settings.minimax_model)
    temperature: float = 0.7
    max_tokens: int = 4096
    _client: AsyncOpenAI | None = field(default=None, repr=False)

    def _ensure_client(self) -> AsyncOpenAI:
        """Lazily initialize the OpenAI client, checking for API key."""
        if self._client is not None:
            return self._client

        if not settings.minimax_api_key:
            msg = (
                "MiniMax API key not configured. "
                "Set MINIMAX_API_KEY in your environment or .env file."
            )
            raise LLMNotConfiguredError(msg)

        self._client = AsyncOpenAI(
            api_key=settings.minimax_api_key,
            base_url=settings.minimax_base_url,
        )
        return self._client

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        """Send a chat completion request and return the full response.

        Args:
            messages: Conversation history as a list of LLMMessage.
            temperature: Override default temperature.
            max_tokens: Override default max tokens.
            model: Override default model.

        Returns:
            LLMResponse with content and token usage.

        Raises:
            LLMNotConfiguredError: If API key is missing.
            LLMAPIError: If the API returns an error.
        """
        client = self._ensure_client()

        try:
            response = await client.chat.completions.create(
                model=model or self.model,
                messages=_to_api_messages(messages),  # type: ignore[arg-type]
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=max_tokens or self.max_tokens,
                stream=False,
            )
        except (APIError, APIConnectionError, RateLimitError) as e:
            raise LLMAPIError(str(e)) from e

        choice = response.choices[0]  # type: ignore[union-attr]
        usage = response.usage  # type: ignore[union-attr]

        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,  # type: ignore[union-attr]
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            finish_reason=choice.finish_reason or "",
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream a chat completion, yielding content chunks as they arrive.

        Args:
            messages: Conversation history as a list of LLMMessage.
            temperature: Override default temperature.
            max_tokens: Override default max tokens.
            model: Override default model.

        Yields:
            Content string chunks as they arrive from the API.

        Raises:
            LLMNotConfiguredError: If API key is missing.
            LLMAPIError: If the API returns an error.
        """
        client = self._ensure_client()

        try:
            response_stream = await client.chat.completions.create(
                model=model or self.model,
                messages=_to_api_messages(messages),  # type: ignore[arg-type]
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=max_tokens or self.max_tokens,
                stream=True,
            )
        except (APIError, APIConnectionError, RateLimitError) as e:
            raise LLMAPIError(str(e)) from e

        async for chunk in response_stream:  # type: ignore[union-attr]
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.close()
            self._client = None
