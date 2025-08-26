"""
Context Window Manager for LinkedIn Article Generator

This module provides centralized context window management for all components
in the LinkedIn Article Generator system. It implements fixed percentage
allocation and provides validation to prevent context window overflow.

Key Features:
- Fixed allocation: 25% output, 15% instructions, 35% RAG, 25% safety
- Character-based estimation (4 chars ≈ 1 token)
- Clear error handling when limits exceeded
- Basic monitoring with warnings at 80% usage
"""

from dataclasses import dataclass
from typing import Dict, Optional, Any
from dspy_factory import DspyModelConfig


class ContextWindowError(Exception):
    """Exception raised when content exceeds context window limits."""

    pass


@dataclass
class ContextWindowBudget:
    """
    Represents the allocated budget for different types of content
    within a model's context window.
    """

    total_tokens: int
    output_tokens: int  # 25% allocation for LLM response generation
    instruction_tokens: int  # 15% allocation for DSPy signatures and prompts
    rag_tokens: int  # 35% allocation for RAG context and citations
    safety_tokens: int  # 25% allocation for safety margin and overhead

    # Character equivalents (4 chars ≈ 1 token)
    total_chars: int
    output_chars: int
    instruction_chars: int
    rag_chars: int
    safety_chars: int


class ContextWindowManager:
    """
    Centralized context window management for the LinkedIn Article Generator.

    Provides unified allocation strategy and validation across all components
    to prevent context window overflow and ensure consistent behavior.
    """

    # Fixed allocation percentages
    OUTPUT_PERCENTAGE = 0.25  # 25% for output tokens
    INSTRUCTION_PERCENTAGE = 0.15  # 15% for instructions/prompts
    RAG_PERCENTAGE = 0.35  # 35% for RAG context
    SAFETY_PERCENTAGE = 0.25  # 25% for safety margin

    # Character to token conversion ratio
    CHARS_PER_TOKEN = 4

    # Warning threshold (80% of available space)
    WARNING_THRESHOLD = 0.8

    def __init__(self, model_config: DspyModelConfig):
        """
        Initialize context window manager with model configuration.

        Args:
            model_config: DSPy model configuration containing context window info
        """
        self.model_config = model_config
        self.context_window = model_config.context_window
        self.max_output_tokens = model_config.max_output_tokens
        self._budget = self._calculate_budget()

    def _calculate_budget(self) -> ContextWindowBudget:
        """Calculate token and character budgets based on fixed percentages."""
        total_tokens = self.context_window

        # Calculate token allocations
        output_tokens = int(total_tokens * self.OUTPUT_PERCENTAGE)
        instruction_tokens = int(total_tokens * self.INSTRUCTION_PERCENTAGE)
        rag_tokens = int(total_tokens * self.RAG_PERCENTAGE)
        safety_tokens = int(total_tokens * self.SAFETY_PERCENTAGE)

        # Convert to character equivalents
        total_chars = total_tokens * self.CHARS_PER_TOKEN
        output_chars = output_tokens * self.CHARS_PER_TOKEN
        instruction_chars = instruction_tokens * self.CHARS_PER_TOKEN
        rag_chars = rag_tokens * self.CHARS_PER_TOKEN
        safety_chars = safety_tokens * self.CHARS_PER_TOKEN

        return ContextWindowBudget(
            total_tokens=total_tokens,
            output_tokens=output_tokens,
            instruction_tokens=instruction_tokens,
            rag_tokens=rag_tokens,
            safety_tokens=safety_tokens,
            total_chars=total_chars,
            output_chars=output_chars,
            instruction_chars=instruction_chars,
            rag_chars=rag_chars,
            safety_chars=safety_chars,
        )

    def get_budget(self) -> ContextWindowBudget:
        """Get the current context window budget allocation."""
        return self._budget

    def get_rag_limit(self) -> int:
        """
        Get the character limit for RAG content (35% allocation).

        Returns:
            Maximum characters allowed for RAG context
        """
        return self._budget.rag_chars

    def get_passage_limit(self) -> int:
        """
        Get the character limit for individual passage processing in DSPy.

        This accounts for instruction overhead and ensures individual passages
        can be processed without exceeding context limits.

        Returns:
            Maximum characters for a single passage in DSPy processing
        """
        # Available space = total - output - safety margin
        available_tokens = (
            self._budget.total_tokens
            - self._budget.output_tokens
            - self._budget.safety_tokens
        )

        # Reserve space for DSPy instructions (~1000 tokens)
        instruction_overhead = 1000
        passage_tokens = available_tokens - instruction_overhead

        # Convert to characters and ensure reasonable bounds
        passage_chars = passage_tokens * self.CHARS_PER_TOKEN
        return max(5000, min(passage_chars, 50000))  # 5K-50K char range

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text using character-based conversion.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0
        return len(text) // self.CHARS_PER_TOKEN

    def validate_content(self, content_parts: Dict[str, str]) -> bool:
        """
        Validate that combined content fits within context window budget.

        Args:
            content_parts: Dictionary of content parts to validate
                          e.g., {'draft': '...', 'context': '...', 'criteria': '...'}

        Returns:
            True if content fits within limits

        Raises:
            ContextWindowError: If content exceeds context window limits
        """
        total_chars = sum(len(content) for content in content_parts.values() if content)
        total_tokens = self.estimate_tokens_from_chars(total_chars)

        # Calculate available space (total - output - safety)
        available_tokens = (
            self._budget.total_tokens
            - self._budget.output_tokens
            - self._budget.safety_tokens
        )

        # Check if content exceeds available space
        if total_tokens > available_tokens:
            raise ContextWindowError(
                f"Content exceeds context window limits: "
                f"{total_tokens:,} tokens required, "
                f"{available_tokens:,} tokens available. "
                f"Content breakdown: {self._format_content_breakdown(content_parts)}"
            )

        # Check if approaching warning threshold
        usage_ratio = total_tokens / available_tokens
        if usage_ratio > self.WARNING_THRESHOLD:
            print(
                f"⚠️ Context window usage warning: {usage_ratio:.1%} of available space used "
                f"({total_tokens:,}/{available_tokens:,} tokens)"
            )

        return True

    def estimate_tokens_from_chars(self, char_count: int) -> int:
        """Convert character count to estimated token count."""
        return char_count // self.CHARS_PER_TOKEN

    def chars_to_tokens(self, char_count: int) -> int:
        """
        Convert character count to estimated token count using the model's character-to-token ratio.

        This is a helper function that provides a simple way to estimate how many tokens
        a text of a given length might use. Uses the standard ratio of 4 characters per token.

        Args:
            char_count: Number of characters to convert to tokens

        Returns:
            Estimated number of tokens
        """
        return self.estimate_tokens_from_chars(char_count)

    def _format_content_breakdown(self, content_parts: Dict[str, str]) -> str:
        """Format content breakdown for error messages."""
        breakdown_parts = []
        for name, content in content_parts.items():
            if content:
                char_count = len(content)
                token_count = self.estimate_tokens_from_chars(char_count)
                breakdown_parts.append(f"{name}: {token_count:,} tokens")
        return ", ".join(breakdown_parts)

    def get_model_info(self) -> Dict[str, Any]:
        """Get model configuration information."""
        return {
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "model_name": self.model_config.name,
        }

    def print_budget_summary(self) -> None:
        """Print a summary of the context window budget allocation."""
        budget = self._budget
        print("📊 Context Window Budget Summary")
        print("=" * 40)
        print(f"Model: {self.model_config.name}")
        print(
            f"Total Context: {budget.total_tokens:,} tokens ({budget.total_chars:,} chars)"
        )
        print()
        print("Allocation Breakdown:")
        print(
            f"  Output (25%):      {budget.output_tokens:,} tokens ({budget.output_chars:,} chars)"
        )
        print(
            f"  Instructions (15%): {budget.instruction_tokens:,} tokens ({budget.instruction_chars:,} chars)"
        )
        print(
            f"  RAG Context (35%):  {budget.rag_tokens:,} tokens ({budget.rag_chars:,} chars)"
        )
        print(
            f"  Safety Margin (25%): {budget.safety_tokens:,} tokens ({budget.safety_chars:,} chars)"
        )
        print()
        print(f"RAG Limit: {self.get_rag_limit():,} characters")
        print(f"Passage Limit: {self.get_passage_limit():,} characters")


if __name__ == "__main__":
    # Example usage and testing
    from dspy_factory import get_openrouter_model

    print("Testing Context Window Manager...")
    print("=" * 50)

    # Test with a sample model
    model_config = get_openrouter_model("openrouter/moonshotai/kimi-k2:free")
    if model_config:
        manager = ContextWindowManager(model_config)
        manager.print_budget_summary()

        # Test validation
        print("\n🧪 Testing Content Validation:")
        test_content = {
            "draft": "This is a test article draft. " * 100,
            "context": "This is RAG context. " * 200,
            "criteria": "Scoring criteria text. " * 50,
        }

        try:
            manager.validate_content(test_content)
            print("✅ Content validation passed")
        except ContextWindowError as e:
            print(f"❌ Content validation failed: {e}")
    else:
        print("❌ Could not load model configuration for testing")
