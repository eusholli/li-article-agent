# dspy-factory.py
"""
DSPy Provider Setup Utility

This module provides a utility function for setting up DSPy with various LLM providers.
It can be imported and used by other programs that need DSPy configuration.
"""

import os
import sys

import dspy  # The main DSPy library for working with language models
from dotenv import load_dotenv  # For loading environment variables from .env file

# Load environment variables from .env file (contains API keys)
load_dotenv()


def setup_dspy_provider(
    model_name: str = "openrouter/moonshotai/kimi-k2:free",
) -> dspy.LM:
    """
    Configure DSPy with an available LLM provider.

    DSPy supports many providers (OpenAI, Anthropic, OpenRouter, etc.)
    This function tries to connect to OpenRouter, which provides access
    to many different models through a single API.

    Args:
        model_name: The model to use (default: free Moonshot AI model)

    Returns:
        dspy.LM: Configured DSPy Language Model object.

    Raises:
        SystemExit: If no API key is found in environment variables
    """
    # Check if we have an OpenRouter API key in our environment variables
    if os.getenv("OPENROUTER_API_KEY"):
        print("✅ Configuring DSPy with OpenRouter...")

        # Create a DSPy Language Model object
        # Format: "provider/model_name"
        # Here we use a free model from Moonshot AI via OpenRouter
        lm = dspy.LM(
            model=model_name,
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )

        # Configure DSPy to use this language model globally
        dspy.configure(lm=lm)
        return lm
    else:
        print("❌ No OpenRouter API key found in environment variables.")
        print("Please add OPENROUTER_API_KEY to your .env file")
        sys.exit(1)


if __name__ == "__main__":
    # Simple test when run directly
    print("Testing DSPy provider setup...")
    lm = setup_dspy_provider()
    print(f"✅ Successfully configured DSPy with model: {lm.model}")
