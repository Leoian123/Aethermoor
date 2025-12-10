"""
LLM Interface - A unified interface for multiple LLM providers.

Supports:
- Anthropic Claude
- OpenAI GPT
- xAI Grok
- Custom/Local LLMs (OpenAI-compatible endpoints)
"""

from .base import (
    BaseLLMProvider,
    GenerationConfig,
    GenerationResponse,
    Message,
)
from .providers import (
    ClaudeProvider,
    OpenAIProvider,
    GrokProvider,
    CustomLLMProvider,
)

__version__ = "0.1.0"
__all__ = [
    "BaseLLMProvider",
    "GenerationConfig",
    "GenerationResponse",
    "Message",
    "ClaudeProvider",
    "OpenAIProvider",
    "GrokProvider",
    "CustomLLMProvider",
]
