"""
Custom/Local LLM Provider.

Supports OpenAI-compatible endpoints like:
- Ollama
- LM Studio
- vLLM
- Text Generation WebUI
- LocalAI
- Any OpenAI-compatible server

Requires: pip install openai (for API compatibility)
          pip install httpx (for direct HTTP calls if needed)
"""

import os
from typing import AsyncIterator

from ..base import (
    BaseLLMProvider,
    GenerationConfig,
    GenerationResponse,
    Message,
)


class CustomLLMProvider(BaseLLMProvider):
    """
    Provider for custom/local LLMs using OpenAI-compatible API.

    This provider works with any server that implements the OpenAI chat
    completions API, including:
    - Ollama (http://localhost:11434/v1)
    - LM Studio (http://localhost:1234/v1)
    - vLLM (http://localhost:8000/v1)
    - Text Generation WebUI (http://localhost:5000/v1)
    - LocalAI (http://localhost:8080/v1)

    Usage:
        # With Ollama
        provider = CustomLLMProvider(
            base_url="http://localhost:11434/v1",
            default_model="llama3.2"
        )
        response = provider.chat("Hello!")

        # With LM Studio
        provider = CustomLLMProvider(
            base_url="http://localhost:1234/v1",
            default_model="local-model"
        )
    """

    # Common local server configurations
    PRESETS = {
        "ollama": {
            "base_url": "http://localhost:11434/v1",
            "default_model": "llama3.2",
        },
        "lmstudio": {
            "base_url": "http://localhost:1234/v1",
            "default_model": "local-model",
        },
        "vllm": {
            "base_url": "http://localhost:8000/v1",
            "default_model": "default",
        },
        "textgen": {
            "base_url": "http://localhost:5000/v1",
            "default_model": "default",
        },
        "localai": {
            "base_url": "http://localhost:8080/v1",
            "default_model": "gpt-3.5-turbo",
        },
    }

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        default_model: str | None = None,
        preset: str | None = None,
        available_models: list[str] | None = None,
    ):
        """
        Initialize Custom LLM provider.

        Args:
            base_url: API endpoint URL (e.g., "http://localhost:11434/v1")
            api_key: API key if required (many local servers don't need one)
            default_model: Default model name to use
            preset: Use a preset configuration ("ollama", "lmstudio", "vllm", etc.)
            available_models: List of available models (for list_models())
        """
        # Apply preset if specified
        if preset:
            if preset not in self.PRESETS:
                raise ValueError(
                    f"Unknown preset: {preset}. "
                    f"Available: {list(self.PRESETS.keys())}"
                )
            preset_config = self.PRESETS[preset]
            base_url = base_url or preset_config["base_url"]
            default_model = default_model or preset_config["default_model"]

        # Get from environment if not provided
        base_url = base_url or os.getenv("CUSTOM_LLM_BASE_URL")
        api_key = api_key or os.getenv("CUSTOM_LLM_API_KEY", "not-needed")

        if not base_url:
            raise ValueError(
                "base_url required. Set CUSTOM_LLM_BASE_URL env var, "
                "pass base_url, or use a preset."
            )

        super().__init__(api_key, base_url)

        self._default_model = default_model or "default"
        self._available_models = available_models or []
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
        return f"Custom LLM ({self.base_url})"

    @property
    def default_model(self) -> str:
        return self._default_model

    def list_models(self) -> list[str]:
        """
        Return available models.

        If available_models was provided at init, returns those.
        Otherwise, attempts to fetch from the server's /models endpoint.
        """
        if self._available_models:
            return self._available_models.copy()

        # Try to fetch from server
        try:
            client = self._get_client()
            models = client.models.list()
            return [model.id for model in models.data]
        except Exception:
            return [self._default_model]

    def _prepare_messages(self, messages: list[Message]) -> list[dict]:
        """Convert messages to OpenAI-compatible format."""
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def generate(
        self,
        messages: list[Message],
        model: str | None = None,
        config: GenerationConfig | None = None,
    ) -> GenerationResponse:
        """Generate a response using the custom LLM."""
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
                "total_tokens": getattr(response.usage, "total_tokens", None),
            }

        return GenerationResponse(
            content=choice.message.content or "",
            model=response.model or model,
            usage=usage,
            finish_reason=choice.finish_reason,
            raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
        )

    async def generate_async(
        self,
        messages: list[Message],
        model: str | None = None,
        config: GenerationConfig | None = None,
    ) -> GenerationResponse:
        """Async generate a response using the custom LLM."""
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
                "total_tokens": getattr(response.usage, "total_tokens", None),
            }

        return GenerationResponse(
            content=choice.message.content or "",
            model=response.model or model,
            usage=usage,
            finish_reason=choice.finish_reason,
            raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
        )

    async def generate_stream(
        self,
        messages: list[Message],
        model: str | None = None,
        config: GenerationConfig | None = None,
    ) -> AsyncIterator[str]:
        """Stream response from the custom LLM."""
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


# Convenience aliases for common local LLM servers
class OllamaProvider(CustomLLMProvider):
    """Pre-configured provider for Ollama."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        default_model: str = "llama3.2",
        **kwargs,
    ):
        super().__init__(
            base_url=base_url,
            default_model=default_model,
            **kwargs,
        )

    @property
    def provider_name(self) -> str:
        return "Ollama"


class LMStudioProvider(CustomLLMProvider):
    """Pre-configured provider for LM Studio."""

    def __init__(
        self,
        base_url: str = "http://localhost:1234/v1",
        default_model: str = "local-model",
        **kwargs,
    ):
        super().__init__(
            base_url=base_url,
            default_model=default_model,
            **kwargs,
        )

    @property
    def provider_name(self) -> str:
        return "LM Studio"
