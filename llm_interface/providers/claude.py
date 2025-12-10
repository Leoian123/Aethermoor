"""
Anthropic Claude LLM Provider.

Requires: pip install anthropic
"""

import os
from typing import AsyncIterator

from ..base import (
    BaseLLMProvider,
    GenerationConfig,
    GenerationResponse,
    Message,
)


class ClaudeProvider(BaseLLMProvider):
    """
    Provider for Anthropic's Claude models.

    Usage:
        provider = ClaudeProvider(api_key="your-api-key")
        response = provider.chat("Hello, Claude!")
    """

    AVAILABLE_MODELS = [
        "claude-sonnet-4-20250514",
        "claude-opus-4-20250514",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-haiku-20240307",
    ]

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        """
        Initialize Claude provider.

        Args:
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
            base_url: Custom API endpoint (optional)
        """
        super().__init__(api_key, base_url)
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

        if not self.api_key:
            raise ValueError(
                "API key required. Set ANTHROPIC_API_KEY env var or pass api_key."
            )

        self._client = None
        self._async_client = None

    def _get_client(self):
        """Lazy initialization of sync client."""
        if self._client is None:
            try:
                import anthropic
            except ImportError:
                raise ImportError("Install anthropic: pip install anthropic")

            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = anthropic.Anthropic(**kwargs)
        return self._client

    def _get_async_client(self):
        """Lazy initialization of async client."""
        if self._async_client is None:
            try:
                import anthropic
            except ImportError:
                raise ImportError("Install anthropic: pip install anthropic")

            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._async_client = anthropic.AsyncAnthropic(**kwargs)
        return self._async_client

    @property
    def provider_name(self) -> str:
        return "Anthropic Claude"

    @property
    def default_model(self) -> str:
        return "claude-sonnet-4-20250514"

    def list_models(self) -> list[str]:
        return self.AVAILABLE_MODELS.copy()

    def _prepare_messages(
        self, messages: list[Message]
    ) -> tuple[str | None, list[dict]]:
        """
        Prepare messages for Claude API.

        Claude requires system message to be separate from the messages list.
        """
        system_content = None
        api_messages = []

        for msg in messages:
            if msg.role == "system":
                system_content = msg.content
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

        return system_content, api_messages

    def generate(
        self,
        messages: list[Message],
        model: str | None = None,
        config: GenerationConfig | None = None,
    ) -> GenerationResponse:
        """Generate a response using Claude."""
        config = config or GenerationConfig()
        model = model or self.default_model
        system_content, api_messages = self._prepare_messages(messages)

        client = self._get_client()

        kwargs = {
            "model": model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "top_p": config.top_p,
            "messages": api_messages,
        }

        if system_content:
            kwargs["system"] = system_content

        if config.stop_sequences:
            kwargs["stop_sequences"] = config.stop_sequences

        response = client.messages.create(**kwargs)

        return GenerationResponse(
            content=response.content[0].text,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            finish_reason=response.stop_reason,
            raw_response=response.model_dump(),
        )

    async def generate_async(
        self,
        messages: list[Message],
        model: str | None = None,
        config: GenerationConfig | None = None,
    ) -> GenerationResponse:
        """Async generate a response using Claude."""
        config = config or GenerationConfig()
        model = model or self.default_model
        system_content, api_messages = self._prepare_messages(messages)

        client = self._get_async_client()

        kwargs = {
            "model": model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "top_p": config.top_p,
            "messages": api_messages,
        }

        if system_content:
            kwargs["system"] = system_content

        if config.stop_sequences:
            kwargs["stop_sequences"] = config.stop_sequences

        response = await client.messages.create(**kwargs)

        return GenerationResponse(
            content=response.content[0].text,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            finish_reason=response.stop_reason,
            raw_response=response.model_dump(),
        )

    async def generate_stream(
        self,
        messages: list[Message],
        model: str | None = None,
        config: GenerationConfig | None = None,
    ) -> AsyncIterator[str]:
        """Stream response from Claude."""
        config = config or GenerationConfig()
        model = model or self.default_model
        system_content, api_messages = self._prepare_messages(messages)

        client = self._get_async_client()

        kwargs = {
            "model": model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "top_p": config.top_p,
            "messages": api_messages,
            "stream": True,
        }

        if system_content:
            kwargs["system"] = system_content

        if config.stop_sequences:
            kwargs["stop_sequences"] = config.stop_sequences

        async with client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text
