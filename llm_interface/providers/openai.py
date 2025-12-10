"""
OpenAI GPT LLM Provider.

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


class OpenAIProvider(BaseLLMProvider):
    """
    Provider for OpenAI's GPT models.

    Usage:
        provider = OpenAIProvider(api_key="your-api-key")
        response = provider.chat("Hello, GPT!")
    """

    AVAILABLE_MODELS = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
        "o1",
        "o1-mini",
        "o1-preview",
    ]

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        organization: str | None = None,
    ):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            base_url: Custom API endpoint (optional)
            organization: OpenAI organization ID (optional)
        """
        super().__init__(api_key, base_url)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.organization = organization or os.getenv("OPENAI_ORG_ID")

        if not self.api_key:
            raise ValueError(
                "API key required. Set OPENAI_API_KEY env var or pass api_key."
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

            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            if self.organization:
                kwargs["organization"] = self.organization
            self._client = openai.OpenAI(**kwargs)
        return self._client

    def _get_async_client(self):
        """Lazy initialization of async client."""
        if self._async_client is None:
            try:
                import openai
            except ImportError:
                raise ImportError("Install openai: pip install openai")

            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            if self.organization:
                kwargs["organization"] = self.organization
            self._async_client = openai.AsyncOpenAI(**kwargs)
        return self._async_client

    @property
    def provider_name(self) -> str:
        return "OpenAI"

    @property
    def default_model(self) -> str:
        return "gpt-4o"

    def list_models(self) -> list[str]:
        return self.AVAILABLE_MODELS.copy()

    def _prepare_messages(self, messages: list[Message]) -> list[dict]:
        """Convert messages to OpenAI format."""
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def generate(
        self,
        messages: list[Message],
        model: str | None = None,
        config: GenerationConfig | None = None,
    ) -> GenerationResponse:
        """Generate a response using OpenAI."""
        config = config or GenerationConfig()
        model = model or self.default_model
        api_messages = self._prepare_messages(messages)

        client = self._get_client()

        kwargs = {
            "model": model,
            "max_completion_tokens": config.max_tokens,
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
        """Async generate a response using OpenAI."""
        config = config or GenerationConfig()
        model = model or self.default_model
        api_messages = self._prepare_messages(messages)

        client = self._get_async_client()

        kwargs = {
            "model": model,
            "max_completion_tokens": config.max_tokens,
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
        """Stream response from OpenAI."""
        config = config or GenerationConfig()
        model = model or self.default_model
        api_messages = self._prepare_messages(messages)

        client = self._get_async_client()

        kwargs = {
            "model": model,
            "max_completion_tokens": config.max_tokens,
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
