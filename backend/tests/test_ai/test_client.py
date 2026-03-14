"""Tests for the AI LLM client wrapper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.client import LLMAPIError, LLMClient, LLMMessage, LLMNotConfiguredError


class TestLLMClientConfiguration:
    """Tests for client configuration and error handling."""

    def test_raises_when_api_key_not_set(self) -> None:
        client = LLMClient()
        with patch("app.ai.client.settings") as mock_settings:
            mock_settings.minimax_api_key = ""
            with pytest.raises(LLMNotConfiguredError, match="API key not configured"):
                client._ensure_client()

    def test_creates_openai_client_when_key_set(self) -> None:
        client = LLMClient()
        with patch("app.ai.client.settings") as mock_settings:
            mock_settings.minimax_api_key = "test-key-123"
            mock_settings.minimax_base_url = "https://api.minimax.chat/v1"
            openai_client = client._ensure_client()
            assert openai_client is not None

    def test_reuses_existing_client(self) -> None:
        client = LLMClient()
        with patch("app.ai.client.settings") as mock_settings:
            mock_settings.minimax_api_key = "test-key-123"
            mock_settings.minimax_base_url = "https://api.minimax.chat/v1"
            first = client._ensure_client()
            second = client._ensure_client()
            assert first is second


class TestLLMClientComplete:
    """Tests for the complete() method."""

    async def test_complete_returns_response(self) -> None:
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello, world!"
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 5
        mock_usage.total_tokens = 15

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "MiniMax-M2.5"

        mock_openai = AsyncMock()
        mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

        client = LLMClient()
        client._client = mock_openai

        messages = [LLMMessage(role="user", content="Hi")]
        result = await client.complete(messages)

        assert result.content == "Hello, world!"
        assert result.model == "MiniMax-M2.5"
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 5
        assert result.total_tokens == 15
        assert result.finish_reason == "stop"

    async def test_complete_passes_overrides(self) -> None:
        mock_choice = MagicMock()
        mock_choice.message.content = "response"
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None
        mock_response.model = "custom-model"

        mock_openai = AsyncMock()
        mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

        client = LLMClient()
        client._client = mock_openai

        messages = [LLMMessage(role="user", content="Hi")]
        await client.complete(
            messages, temperature=0.1, max_tokens=100, model="custom-model"
        )

        call_kwargs = mock_openai.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "custom-model"
        assert call_kwargs["temperature"] == 0.1
        assert call_kwargs["max_tokens"] == 100

    async def test_complete_handles_api_error(self) -> None:
        from openai import APIError

        mock_openai = AsyncMock()
        mock_openai.chat.completions.create = AsyncMock(
            side_effect=APIError(
                message="Rate limit exceeded",
                request=MagicMock(),
                body=None,
            )
        )

        client = LLMClient()
        client._client = mock_openai

        messages = [LLMMessage(role="user", content="Hi")]
        with pytest.raises(LLMAPIError):
            await client.complete(messages)

    async def test_complete_handles_null_usage(self) -> None:
        mock_choice = MagicMock()
        mock_choice.message.content = "response"
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None
        mock_response.model = "test"

        mock_openai = AsyncMock()
        mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

        client = LLMClient()
        client._client = mock_openai

        result = await client.complete([LLMMessage(role="user", content="Hi")])
        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0


class TestLLMClientStream:
    """Tests for the stream() method."""

    async def test_stream_yields_chunks(self) -> None:
        # Create mock stream chunks
        chunks = []
        for text in ["Hello", ", ", "world", "!"]:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = text
            chunks.append(chunk)

        # Final chunk with no content
        final_chunk = MagicMock()
        final_chunk.choices = [MagicMock()]
        final_chunk.choices[0].delta.content = None
        chunks.append(final_chunk)

        async def mock_stream() -> None:
            for c in chunks:
                yield c

        mock_openai = AsyncMock()
        mock_openai.chat.completions.create = AsyncMock(return_value=mock_stream())

        client = LLMClient()
        client._client = mock_openai

        collected: list[str] = []
        async for chunk_text in client.stream(
            [LLMMessage(role="user", content="Hi")]
        ):
            collected.append(chunk_text)

        assert collected == ["Hello", ", ", "world", "!"]


class TestLLMClientClose:
    """Tests for the close() method."""

    async def test_close_cleans_up_client(self) -> None:
        mock_openai = AsyncMock()

        client = LLMClient()
        client._client = mock_openai

        await client.close()
        assert client._client is None
        mock_openai.close.assert_called_once()

    async def test_close_no_op_when_no_client(self) -> None:
        client = LLMClient()
        await client.close()  # Should not raise
