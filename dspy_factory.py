# dspy-factory.py
"""
DSPy Provider Setup Utility with Context Window Management

This module provides enhanced DSPy configuration with context window awareness.
It can be imported and used by other programs that need DSPy configuration
with intelligent context management.
"""

import os
import sys
from typing import Dict, Any, Optional

import dspy  # The main DSPy library for working with language models
from dotenv import load_dotenv  # For loading environment variables from .env file

# Load environment variables from .env file (contains API keys)
load_dotenv()

# Model configurations with context windows and other metadata
MODEL_CONFIGS: Dict[str, Dict[str, Any]] = {
    "openrouter/moonshotai/kimi-k2:free": {
        "context_window": 32000,
        "max_output_tokens": 4000,  # Conservative estimate for generation
        "cost_per_token": 0.0,  # Free model
        "provider": "openrouter",
        "description": "Moonshot AI Kimi K2 - Free tier with 32K context",
    },
    "openrouter/anthropic/claude-3-haiku": {
        "context_window": 200000,
        "max_output_tokens": 4096,
        "cost_per_token": 0.00025,
        "provider": "openrouter",
        "description": "Claude 3 Haiku - Fast and efficient",
    },
    "openrouter/anthropic/claude-3-sonnet": {
        "context_window": 200000,
        "max_output_tokens": 4096,
        "cost_per_token": 0.003,
        "provider": "openrouter",
        "description": "Claude 3 Sonnet - Balanced performance",
    },
    "openrouter/openai/gpt-4o": {
        "context_window": 128000,
        "max_output_tokens": 4096,
        "cost_per_token": 0.005,
        "provider": "openrouter",
        "description": "GPT-4o - Latest OpenAI model",
    },
    "openrouter/openai/gpt-3.5-turbo": {
        "context_window": 16385,
        "max_output_tokens": 4096,
        "cost_per_token": 0.0005,
        "provider": "openrouter",
        "description": "GPT-3.5 Turbo - Cost effective",
    },
}


class ConfiguredLM:
    """
    Enhanced DSPy Language Model wrapper with context window awareness.

    This class wraps a DSPy LM object and provides additional functionality
    for managing context windows, token estimation, and available space calculation.
    """

    def __init__(self, model_name: str):
        """
        Initialize the configured language model.

        Args:
            model_name: The model identifier (e.g., "openrouter/moonshotai/kimi-k2:free")
        """
        self.model_name = model_name
        self.config = MODEL_CONFIGS.get(model_name, {})

        # Create the underlying DSPy LM object
        self.lm = dspy.LM(
            model=model_name,
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )

        # Extract configuration with sensible defaults
        self.context_window = self.config.get("context_window", 4096)
        self.max_output_tokens = self.config.get("max_output_tokens", 2000)
        self.cost_per_token = self.config.get("cost_per_token", 0.001)
        self.provider = self.config.get("provider", "unknown")
        self.description = self.config.get("description", f"Model: {model_name}")

    def get_context_window(self) -> int:
        """Get the total context window size in tokens."""
        return self.context_window

    def get_max_output_tokens(self) -> int:
        """Get the maximum output tokens for this model."""
        return self.max_output_tokens

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in a text string.

        This is a rough approximation: ~1.3 tokens per word for English text.
        For more accurate counting, you'd need the actual tokenizer.

        Args:
            text: The text to estimate tokens for

        Returns:
            Estimated number of tokens
        """
        if not text:
            return 0

        # Rough estimation: 1.3 tokens per word on average
        word_count = len(text.split())
        estimated_tokens = int(word_count * 1.3)

        # Add some tokens for formatting, special characters, etc.
        return estimated_tokens + 50

    def get_available_context(self, current_input_tokens: int) -> int:
        """
        Calculate available context window space for additional input.

        Args:
            current_input_tokens: Number of tokens already used in input

        Returns:
            Number of tokens available for additional input
        """
        reserved_for_output = self.max_output_tokens
        used_tokens = current_input_tokens + reserved_for_output
        available = max(0, self.context_window - used_tokens)
        return available

    def check_context_fits(self, text: str, additional_tokens: int = 0) -> bool:
        """
        Check if text fits within the context window.

        Args:
            text: The text to check
            additional_tokens: Additional tokens to account for (e.g., prompts)

        Returns:
            True if text fits, False otherwise
        """
        estimated_tokens = self.estimate_tokens(text) + additional_tokens
        return self.get_available_context(estimated_tokens) > 0

    def truncate_to_fit(
        self, text: str, additional_tokens: int = 0, preserve_end: bool = False
    ) -> str:
        """
        Truncate text to fit within context window if needed.

        Args:
            text: The text to potentially truncate
            additional_tokens: Additional tokens to account for
            preserve_end: If True, keep the end of text; if False, keep the beginning

        Returns:
            Truncated text that fits within context window
        """
        if self.check_context_fits(text, additional_tokens):
            return text

        # Calculate maximum allowed tokens for the text
        max_text_tokens = (
            self.context_window - self.max_output_tokens - additional_tokens - 100
        )  # Safety margin

        if max_text_tokens <= 0:
            return ""

        # Rough conversion back to words (divide by 1.3)
        max_words = int(max_text_tokens / 1.3)

        words = text.split()
        if len(words) <= max_words:
            return text

        if preserve_end:
            # Keep the end of the text
            truncated_words = words[-max_words:]
            return "..." + " ".join(truncated_words)
        else:
            # Keep the beginning of the text
            truncated_words = words[:max_words]
            return " ".join(truncated_words) + "..."

    def get_model_info(self) -> Dict[str, Any]:
        """Get comprehensive model information."""
        return {
            "model_name": self.model_name,
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "cost_per_token": self.cost_per_token,
            "provider": self.provider,
            "description": self.description,
            "available_context_ratio": lambda input_tokens: self.get_available_context(
                input_tokens
            )
            / self.context_window,
        }

    def __call__(self, *args, **kwargs):
        """Allow the object to be called like the underlying LM."""
        return self.lm(*args, **kwargs)

    def __getattr__(self, name):
        """Delegate attribute access to the underlying LM object."""
        return getattr(self.lm, name)


# Global variable to store the configured LM
_configured_lm: Optional[ConfiguredLM] = None


def setup_dspy_provider(
    model_name: str = "openrouter/moonshotai/kimi-k2:free",
) -> ConfiguredLM:
    """
    Configure DSPy with an available LLM provider and context window awareness.

    DSPy supports many providers (OpenAI, Anthropic, OpenRouter, etc.)
    This function tries to connect to OpenRouter, which provides access
    to many different models through a single API.

    Args:
        model_name: The model to use (default: free Moonshot AI model)

    Returns:
        ConfiguredLM: Enhanced DSPy Language Model object with context awareness.

    Raises:
        SystemExit: If no API key is found in environment variables
    """
    global _configured_lm

    # Check if we have an OpenRouter API key in our environment variables
    if os.getenv("OPENROUTER_API_KEY"):
        print("✅ Configuring DSPy with OpenRouter...")

        # Create enhanced configured LM object
        _configured_lm = ConfiguredLM(model_name)

        # Configure DSPy to use the underlying language model globally
        dspy.configure(lm=_configured_lm.lm)

        # Print configuration info
        config = _configured_lm.config
        context_window = config.get("context_window", "Unknown")
        description = config.get("description", model_name)

        print(f"🤖 Model: {description}")
        print(f"📏 Context window: {context_window:,} tokens")
        print(f"🎯 Max output: {_configured_lm.max_output_tokens:,} tokens")

        return _configured_lm
    else:
        print("❌ No OpenRouter API key found in environment variables.")
        print("Please add OPENROUTER_API_KEY to your .env file")
        sys.exit(1)


def get_current_lm() -> ConfiguredLM:
    """
    Get the currently configured LM with context window info.

    Returns:
        ConfiguredLM: The currently configured language model

    Raises:
        RuntimeError: If DSPy provider not configured
    """
    if _configured_lm is None:
        raise RuntimeError(
            "DSPy provider not configured. Call setup_dspy_provider() first."
        )
    return _configured_lm


def get_context_window() -> int:
    """
    Quick access to context window size.

    Returns:
        int: Context window size in tokens

    Raises:
        RuntimeError: If DSPy provider not configured
    """
    return get_current_lm().get_context_window()


def get_available_models() -> Dict[str, Dict[str, Any]]:
    """
    Get information about all available models.

    Returns:
        Dict mapping model names to their configurations
    """
    return MODEL_CONFIGS.copy()


def estimate_tokens(text: str) -> int:
    """
    Estimate tokens in text using the current model's estimation.

    Args:
        text: Text to estimate tokens for

    Returns:
        Estimated number of tokens
    """
    if _configured_lm:
        return _configured_lm.estimate_tokens(text)
    else:
        # Fallback estimation if no model configured
        return int(len(text.split()) * 1.3) + 50


def check_context_usage(text: str, additional_tokens: int = 0) -> Dict[str, Any]:
    """
    Check context usage for given text.

    Args:
        text: Text to analyze
        additional_tokens: Additional tokens to account for

    Returns:
        Dictionary with usage statistics
    """
    lm = get_current_lm()
    estimated_tokens = lm.estimate_tokens(text) + additional_tokens
    available = lm.get_available_context(estimated_tokens)

    return {
        "estimated_tokens": estimated_tokens,
        "available_tokens": available,
        "context_window": lm.context_window,
        "usage_percentage": (estimated_tokens / lm.context_window) * 100,
        "fits": available > 0,
        "model_name": lm.model_name,
    }


if __name__ == "__main__":
    # Enhanced test when run directly
    print("Testing Enhanced DSPy Provider Setup...")
    print("=" * 50)

    # Test setup
    lm = setup_dspy_provider()
    print(f"✅ Successfully configured DSPy with model: {lm.model_name}")

    # Test context window functions
    print(f"\n📊 Context Window Info:")
    print(f"   Total context: {get_context_window():,} tokens")
    print(f"   Max output: {lm.get_max_output_tokens():,} tokens")

    # Test token estimation
    test_text = "This is a test article with multiple sentences. " * 20
    usage = check_context_usage(test_text)
    print(f"\n🧮 Token Estimation Test:")
    print(f"   Test text tokens: {usage['estimated_tokens']:,}")
    print(f"   Available tokens: {usage['available_tokens']:,}")
    print(f"   Usage: {usage['usage_percentage']:.1f}%")
    print(f"   Fits in context: {usage['fits']}")

    # Test available models
    print(f"\n📋 Available Models:")
    for model_name, config in get_available_models().items():
        context = config.get("context_window", "Unknown")
        desc = config.get("description", model_name)
        print(f"   {model_name}: {context:,} tokens - {desc}")
