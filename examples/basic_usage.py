"""
Basic usage examples for the LLM Interface.

Run with: python -m examples.basic_usage
"""

import asyncio
import os

from llm_interface import (
    ClaudeProvider,
    OpenAIProvider,
    GrokProvider,
    CustomLLMProvider,
    Message,
    GenerationConfig,
)


def example_claude():
    """Example: Using Claude."""
    print("\n" + "=" * 50)
    print("Claude Example")
    print("=" * 50)

    # Requires ANTHROPIC_API_KEY environment variable
    provider = ClaudeProvider()

    # Simple chat
    response = provider.chat(
        prompt="What is the capital of France?",
        system="You are a helpful geography assistant. Be concise.",
    )
    print(f"Response: {response}")

    # With custom configuration
    config = GenerationConfig(
        max_tokens=100,
        temperature=0.5,
    )
    response = provider.chat(
        prompt="List 3 interesting facts about Paris.",
        config=config,
    )
    print(f"\nWith config: {response}")


def example_openai():
    """Example: Using OpenAI."""
    print("\n" + "=" * 50)
    print("OpenAI Example")
    print("=" * 50)

    # Requires OPENAI_API_KEY environment variable
    provider = OpenAIProvider()

    response = provider.chat(
        prompt="Explain quantum computing in one sentence.",
        model="gpt-4o-mini",  # Use a specific model
    )
    print(f"Response: {response}")


def example_grok():
    """Example: Using Grok."""
    print("\n" + "=" * 50)
    print("Grok Example")
    print("=" * 50)

    # Requires XAI_API_KEY environment variable
    provider = GrokProvider()

    response = provider.chat(
        prompt="What makes you different from other AI assistants?",
    )
    print(f"Response: {response}")


def example_custom_ollama():
    """Example: Using Ollama (local LLM)."""
    print("\n" + "=" * 50)
    print("Ollama (Local LLM) Example")
    print("=" * 50)

    # Using preset configuration
    provider = CustomLLMProvider(preset="ollama")

    # Or manual configuration:
    # provider = CustomLLMProvider(
    #     base_url="http://localhost:11434/v1",
    #     default_model="llama3.2",
    # )

    response = provider.chat(
        prompt="Hello! Tell me a short joke.",
    )
    print(f"Response: {response}")


def example_multi_turn_conversation():
    """Example: Multi-turn conversation."""
    print("\n" + "=" * 50)
    print("Multi-turn Conversation Example")
    print("=" * 50)

    provider = ClaudeProvider()

    messages = [
        Message(role="system", content="You are a math tutor."),
        Message(role="user", content="What is 15 * 7?"),
    ]

    # First turn
    response = provider.generate(messages)
    print(f"User: What is 15 * 7?")
    print(f"Assistant: {response.content}")

    # Add assistant response and continue
    messages.append(Message(role="assistant", content=response.content))
    messages.append(Message(role="user", content="Now divide that by 3"))

    # Second turn
    response = provider.generate(messages)
    print(f"\nUser: Now divide that by 3")
    print(f"Assistant: {response.content}")


async def example_async():
    """Example: Async generation."""
    print("\n" + "=" * 50)
    print("Async Example")
    print("=" * 50)

    provider = ClaudeProvider()

    response = await provider.generate_async(
        messages=[Message(role="user", content="Count from 1 to 5.")],
    )
    print(f"Async response: {response.content}")


async def example_streaming():
    """Example: Streaming response."""
    print("\n" + "=" * 50)
    print("Streaming Example")
    print("=" * 50)

    provider = ClaudeProvider()

    print("Streaming: ", end="", flush=True)
    async for chunk in provider.generate_stream(
        messages=[Message(role="user", content="Write a haiku about coding.")],
    ):
        print(chunk, end="", flush=True)
    print()  # Newline at end


def example_compare_providers():
    """Example: Compare responses from different providers."""
    print("\n" + "=" * 50)
    print("Compare Providers Example")
    print("=" * 50)

    prompt = "In exactly 10 words, explain what makes a good API."
    config = GenerationConfig(max_tokens=50, temperature=0.7)

    providers = {}

    # Add available providers
    if os.getenv("ANTHROPIC_API_KEY"):
        providers["Claude"] = ClaudeProvider()
    if os.getenv("OPENAI_API_KEY"):
        providers["OpenAI"] = OpenAIProvider()
    if os.getenv("XAI_API_KEY"):
        providers["Grok"] = GrokProvider()

    for name, provider in providers.items():
        try:
            response = provider.chat(prompt=prompt, config=config)
            print(f"\n{name}: {response}")
        except Exception as e:
            print(f"\n{name}: Error - {e}")


def main():
    """Run examples based on available API keys."""
    print("LLM Interface Examples")
    print("=" * 50)

    # Check which providers are available
    has_claude = bool(os.getenv("ANTHROPIC_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_grok = bool(os.getenv("XAI_API_KEY"))

    print(f"Claude available: {has_claude}")
    print(f"OpenAI available: {has_openai}")
    print(f"Grok available: {has_grok}")

    # Run examples for available providers
    if has_claude:
        example_claude()
        example_multi_turn_conversation()
        asyncio.run(example_async())
        asyncio.run(example_streaming())

    if has_openai:
        example_openai()

    if has_grok:
        example_grok()

    # Compare if multiple providers available
    if sum([has_claude, has_openai, has_grok]) >= 2:
        example_compare_providers()

    # Note about local LLMs
    print("\n" + "=" * 50)
    print("Note: For local LLMs (Ollama, LM Studio), make sure")
    print("the server is running before calling example_custom_ollama()")
    print("=" * 50)


if __name__ == "__main__":
    main()
