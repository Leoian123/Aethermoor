"""
xAI Grok LLM Provider.

Grok uses an OpenAI-compatible API, so we leverage the openai library.
Requires: pip install openai
"""

import os
from typing import AsyncIterator

from ..base import (
    BaseLLMProvider,
    GenerationConfig,
    GenerationResponse,
    Message,
)


class GrokProvider(BaseLLMProvider):
    """
    Provider for xAI's Grok models.

    Grok uses an OpenAI-compatible API endpoint.

    Usage:
        provider = GrokProvider(api_key="your-xai-api-key")
        response = provider.chat("Hello, Grok!")
    """

    XAI_BASE_URL = "https://api.x.ai/v1"

    AVAILABLE_MODELS = [
        "grok-3",
        "grok-3-fast",
        "grok-3-mini",
        "grok-3-mini-fast",
        "grok-2",
        "grok-2-mini",
        "grok-2-vision",
    ]

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        """
        Initialize Grok provider.

        Args:
            api_key: xAI API key (or set XAI_API_KEY env var)
            base_url: Custom API endpoint (defaults to xAI API)
        """
        super().__init__(api_key, base_url or self.XAI_BASE_URL)
        self.api_key = api_key or os.getenv("XAI_API_KEY")

        if not self.api_key:
            raise ValueError(
                "API key required. Set XAI_API_KEY env var or pass api_key."
            )

        self._client = None
        self._async_client = None

    def _get_client(self):
        """Lazy initialization of sync client."""
        if self._client is None:
            try:
                import openai
            except ImportError:
                raise ImportError("Install openai: pip install openai")

            self._client = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client

    def _get_async_client(self):
        """Lazy initialization of async client."""
        if self._async_client is None:
            try:
                import openai
            except ImportError:
                raise ImportError("Install openai: pip install openai")

            self._async_client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._async_client

    @property
    def provider_name(self) -> str:
        return "xAI Grok"

    @property
    def default_model(self) -> str:
        return "grok-3"

    def list_models(self) -> list[str]:
        return self.AVAILABLE_MODELS.copy()

    def _prepare_messages(self, messages: list[Message]) -> list[dict]:
        """Convert messages to OpenAI-compatible format."""
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def generate(
        self,
        messages: list[Message],
        model: str | None = None,
        config: GenerationConfig | None = None,
    ) -> GenerationResponse:
        """Generate a response using Grok."""
        config = config or GenerationConfig()
        model = model or self.default_model
        api_messages = self._prepare_messages(messages)

        client = self._get_client()

        kwargs = {
            "model": model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "top_p": config.top_p,
            "messages": api_messages,
        }

        if config.stop_sequences:
            kwargs["stop"] = config.stop_sequences

        response = client.chat.completions.create(**kwargs)

        choice = response.choices[0]
        usage = None
        if response.usage:
            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return GenerationResponse(
            content=choice.message.content or "",
            model=response.model,
            usage=usage,
            finish_reason=choice.finish_reason,
            raw_response=response.model_dump(),
        )

    async def generate_async(
        self,
        messages: list[Message],
        model: str | None = None,
        config: GenerationConfig | None = None,
    ) -> GenerationResponse:
        """Async generate a response using Grok."""
        config = config or GenerationConfig()
        model = model or self.default_model
        api_messages = self._prepare_messages(messages)

        client = self._get_async_client()

        kwargs = {
            "model": model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "top_p": config.top_p,
            "messages": api_messages,
        }

        if config.stop_sequences:
            kwargs["stop"] = config.stop_sequences

        response = await client.chat.completions.create(**kwargs)

        choice = response.choices[0]
        usage = None
        if response.usage:
            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return GenerationResponse(
            content=choice.message.content or "",
            model=response.model,
            usage=usage,
            finish_reason=choice.finish_reason,
            raw_response=response.model_dump(),
        )

    async def generate_stream(
        self,
        messages: list[Message],
        model: str | None = None,
        config: GenerationConfig | None = None,
    ) -> AsyncIterator[str]:
        """Stream response from Grok."""
        config = config or GenerationConfig()
        model = model or self.default_model
        api_messages = self._prepare_messages(messages)

        client = self._get_async_client()

        kwargs = {
            "model": model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "top_p": config.top_p,
            "messages": api_messages,
            "stream": True,
        }

        if config.stop_sequences:
            kwargs["stop"] = config.stop_sequences

        stream = await client.chat.completions.create(**kwargs)

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
