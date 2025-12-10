"""
Base interface for LLM providers.

This module defines the abstract base class that all LLM providers must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class Message:
    """Represents a chat message."""
    role: str  # "user", "assistant", "system"
    content: str


@dataclass
class GenerationConfig:
    """Configuration for text generation."""
    max_tokens: int = 1024
    temperature: float = 0.7
    top_p: float = 1.0
    stop_sequences: list[str] = field(default_factory=list)
    stream: bool = False


@dataclass
class GenerationResponse:
    """Response from text generation."""
    content: str
    model: str
    usage: dict[str, int] | None = None
    finish_reason: str | None = None
    raw_response: dict | None = None


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All LLM providers must implement this interface to ensure
    consistent behavior across different backends.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        """
        Initialize the provider.

        Args:
            api_key: API key for authentication (optional for local models)
            base_url: Base URL for the API endpoint (optional, uses default if not set)
        """
        self.api_key = api_key
        self.base_url = base_url

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of the provider."""
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return the default model for this provider."""
        ...

    @abstractmethod
    def list_models(self) -> list[str]:
        """Return a list of available models."""
        ...

    @abstractmethod
    def generate(
        self,
        messages: list[Message],
        model: str | None = None,
        config: GenerationConfig | None = None,
    ) -> GenerationResponse:
        """
        Generate a response from the LLM.

        Args:
            messages: List of messages in the conversation
            model: Model to use (uses default if not specified)
            config: Generation configuration

        Returns:
            GenerationResponse with the generated content
        """
        ...

    @abstractmethod
    async def generate_async(
        self,
        messages: list[Message],
        model: str | None = None,
        config: GenerationConfig | None = None,
    ) -> GenerationResponse:
        """
        Async version of generate.

        Args:
            messages: List of messages in the conversation
            model: Model to use (uses default if not specified)
            config: Generation configuration

        Returns:
            GenerationResponse with the generated content
        """
        ...

    @abstractmethod
    async def generate_stream(
        self,
        messages: list[Message],
        model: str | None = None,
        config: GenerationConfig | None = None,
    ) -> AsyncIterator[str]:
        """
        Stream the response from the LLM.

        Args:
            messages: List of messages in the conversation
            model: Model to use (uses default if not specified)
            config: Generation configuration

        Yields:
            Chunks of the generated content
        """
        ...

    def chat(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        config: GenerationConfig | None = None,
    ) -> str:
        """
        Simple chat interface for single-turn conversations.

        Args:
            prompt: The user's message
            system: Optional system prompt
            model: Model to use
            config: Generation configuration

        Returns:
            The assistant's response as a string
        """
        messages = []
        if system:
            messages.append(Message(role="system", content=system))
        messages.append(Message(role="user", content=prompt))

        response = self.generate(messages, model=model, config=config)
        return response.content
