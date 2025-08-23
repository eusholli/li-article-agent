#!/usr/bin/env python3
"""
Word Count Manager for LinkedIn Article Generator

This module manages word count constraints and provides guidance for length adjustments
while maintaining article quality and scoring criteria compliance.
"""

import re
from typing import List, Dict, Any, Tuple, Optional
from li_article_judge import ArticleScoreModel


class WordCountManager:
    """
    Manages word count constraints and provides intelligent length adjustment guidance.

    This class handles the 2000-2500 word target range for LinkedIn articles,
    providing strategic guidance for expansion or condensation while maintaining quality.
    """

    def __init__(self, target_min: int, target_max: int):
        """
        Initialize the word count manager with target range.

        Args:
            target_min: Minimum target word count
            target_max: Maximum target word count
        """
        self.target_min = target_min
        self.target_max = target_max
        self.target_optimal = (target_min + target_max) // 2  # 2250 words

    def count_words(self, text: str) -> int:
        """
        Accurate word counting for articles.

        Uses sophisticated word counting that handles:
        - Contractions as single words
        - Hyphenated words as single words
        - Numbers and alphanumeric strings
        - Proper handling of punctuation

        Args:
            text: Article text to count

        Returns:
            int: Accurate word count
        """
        if not text or not text.strip():
            return 0

        # Remove extra whitespace and normalize
        text = re.sub(r"\s+", " ", text.strip())

        # Split on whitespace and filter out empty strings
        words = [word for word in text.split() if word.strip()]

        # Filter out standalone punctuation marks
        words = [word for word in words if re.search(r"[a-zA-Z0-9]", word)]

        return len(words)

    def is_within_range(self, word_count: int) -> bool:
        """
        Check if word count is within target range.

        Args:
            word_count: Current word count

        Returns:
            bool: True if within target range
        """
        return self.target_min <= word_count <= self.target_max

    def get_word_count_status(self, word_count: int) -> Dict[str, Any]:
        """
        Get comprehensive word count status and guidance.

        Args:
            word_count: Current word count

        Returns:
            Dict with status, guidance, and adjustment recommendations
        """
        status = {
            "current_count": word_count,
            "target_min": self.target_min,
            "target_max": self.target_max,
            "target_optimal": self.target_optimal,
            "within_range": self.is_within_range(word_count),
            "adjustment_needed": None,
            "adjustment_amount": 0,
            "guidance": "",
            "priority": "low",
        }

        if word_count < self.target_min:
            shortage = self.target_min - word_count
            status["adjustment_needed"] = "expand"
            status["adjustment_amount"] = shortage
            status["priority"] = "high" if shortage > 500 else "medium"
            status["guidance"] = (
                f"Article is {shortage} words short. Need to expand content while maintaining quality."
            )

        elif word_count > self.target_max:
            excess = word_count - self.target_max
            status["adjustment_needed"] = "condense"
            status["adjustment_amount"] = excess
            status["priority"] = "high" if excess > 500 else "medium"
            status["guidance"] = (
                f"Article is {excess} words over. Need to condense while preserving key insights."
            )

        else:
            status["guidance"] = (
                f"Word count is within target range ({word_count} words)."
            )

        return status

    def get_adjustment_guidance(self, current_count: int) -> str:
        """
        Provide specific guidance for word count adjustments.

        Args:
            current_count: Current word count

        Returns:
            str: Specific adjustment guidance
        """
        status = self.get_word_count_status(current_count)
        return status["guidance"]

    def suggest_expansion_strategies(
        self, score_results: ArticleScoreModel
    ) -> List[str]:
        """
        Suggest strategic expansion areas based on scoring weaknesses.

        Args:
            score_results: Current scoring results to identify weak areas

        Returns:
            List[str]: Specific expansion strategies that improve both length and scores
        """
        strategies = []

        # Analyze scoring weaknesses for expansion opportunities
        weak_areas = []
        for category, results in score_results.category_scores.items():
            category_avg = sum(r.score for r in results) / len(results)
            if category_avg < 3.5:  # Below good performance
                weak_areas.append((category, category_avg, results))

        # Sort by performance (worst first)
        weak_areas.sort(key=lambda x: x[1])

        if weak_areas:
            strategies.append(
                "STRATEGIC EXPANSION AREAS (improves both length and scores):"
            )

            for category, avg_score, results in weak_areas[:3]:
                strategies.append(f"\n• Expand {category} section:")

                for result in results:
                    if result.score < 3:
                        strategies.append(
                            f"  - Add more detail for: {result.criterion}"
                        )
                        strategies.append(f"    Suggestion: {result.suggestions}")

        # General expansion strategies
        strategies.extend(
            [
                "\nGENERAL EXPANSION TECHNIQUES:",
                "• Add concrete examples and case studies",
                "• Include relevant data and statistics",
                "• Expand on implications and consequences",
                "• Add personal insights and experiences",
                "• Include counterarguments and nuanced perspectives",
                "• Provide step-by-step explanations",
                "• Add historical context or background",
                "• Include quotes from industry experts",
                "• Expand on practical applications",
                "• Add detailed analysis of cause and effect",
            ]
        )

        return strategies

    def suggest_condensation_strategies(self, article_text: str) -> List[str]:
        """
        Suggest strategic condensation approaches that preserve quality.

        Args:
            article_text: Current article text to analyze

        Returns:
            List[str]: Specific condensation strategies
        """
        strategies = [
            "STRATEGIC CONDENSATION APPROACHES:",
            "",
            "• Remove redundant phrases and repetitive statements",
            "• Combine similar points into single, stronger statements",
            "• Eliminate filler words and unnecessary qualifiers",
            "• Condense examples while keeping the most impactful ones",
            "• Merge related paragraphs with similar themes",
            "• Remove tangential points that don't support main thesis",
            "• Shorten transitions while maintaining flow",
            "• Combine bullet points that cover similar concepts",
            "• Eliminate excessive background information",
            "• Condense conclusions without losing key takeaways",
        ]

        # Analyze text for specific condensation opportunities
        word_count = self.count_words(article_text)
        if word_count > 0:
            # Look for potential redundancy patterns
            sentences = re.split(r"[.!?]+", article_text)
            if len(sentences) > 50:  # Many sentences might indicate verbosity
                strategies.append("")
                strategies.append("SPECIFIC OPPORTUNITIES:")
                strategies.append(
                    "• Article has many sentences - look for opportunities to combine related ideas"
                )

            # Check for common redundancy indicators
            redundancy_indicators = [
                ("in other words", "redundant explanations"),
                ("as mentioned", "repetitive references"),
                ("it should be noted", "unnecessary qualifiers"),
                ("obviously", "obvious statements"),
                ("clearly", "unnecessary emphasis"),
            ]

            for indicator, description in redundancy_indicators:
                if indicator in article_text.lower():
                    strategies.append(f"• Remove {description} (found '{indicator}')")

        return strategies

    def get_length_optimization_prompt(
        self, current_count: int, score_results: Optional[ArticleScoreModel] = None
    ) -> str:
        """
        Generate a comprehensive prompt for length optimization.

        Args:
            current_count: Current word count
            score_results: Optional scoring results for targeted guidance

        Returns:
            str: Detailed optimization prompt for LLM
        """
        status = self.get_word_count_status(current_count)
        prompt_parts = []

        prompt_parts.append("WORD COUNT OPTIMIZATION GUIDANCE")
        prompt_parts.append("=" * 40)
        prompt_parts.append(f"Current: {current_count} words")
        prompt_parts.append(f"Target: {self.target_min}-{self.target_max} words")
        prompt_parts.append(f"Optimal: {self.target_optimal} words")
        prompt_parts.append("")

        if status["adjustment_needed"] == "expand":
            prompt_parts.append(
                f"EXPANSION NEEDED: +{status['adjustment_amount']} words"
            )
            prompt_parts.append(
                "Priority: Focus on areas that improve both length AND scoring"
            )
            prompt_parts.append("")

            if score_results is not None:
                expansion_strategies = self.suggest_expansion_strategies(score_results)
                prompt_parts.extend(expansion_strategies)
            else:
                prompt_parts.extend(
                    [
                        "EXPANSION STRATEGIES:",
                        "• Add detailed examples and case studies",
                        "• Expand on implications and consequences",
                        "• Include supporting data and evidence",
                        "• Add personal insights and experiences",
                        "• Provide deeper analysis of key points",
                    ]
                )

        elif status["adjustment_needed"] == "condense":
            prompt_parts.append(
                f"CONDENSATION NEEDED: -{status['adjustment_amount']} words"
            )
            prompt_parts.append(
                "Priority: Remove redundancy while preserving all key insights"
            )
            prompt_parts.append("")

            condensation_strategies = self.suggest_condensation_strategies("")
            prompt_parts.extend(condensation_strategies)

        else:
            prompt_parts.append("✅ WORD COUNT OPTIMAL")
            prompt_parts.append(
                "Focus on quality improvements without major length changes"
            )

        prompt_parts.append("")
        prompt_parts.append("QUALITY MAINTENANCE PRINCIPLES:")
        prompt_parts.append("• Preserve all key insights and arguments")
        prompt_parts.append("• Maintain professional LinkedIn tone")
        prompt_parts.append("• Keep strong examples and evidence")
        prompt_parts.append("• Ensure logical flow and structure")
        prompt_parts.append("• Preserve engagement elements (hooks, CTAs)")

        return "\n".join(prompt_parts)

    def analyze_length_vs_quality_tradeoffs(
        self, word_count: int, score_percentage: float
    ) -> Dict[str, Any]:
        """
        Analyze tradeoffs between length and quality targets.

        Args:
            word_count: Current word count
            score_percentage: Current score percentage

        Returns:
            Dict with tradeoff analysis and recommendations
        """
        length_status = self.get_word_count_status(word_count)

        analysis = {
            "length_achieved": length_status["within_range"],
            "quality_achieved": score_percentage >= 89.0,
            "both_achieved": length_status["within_range"] and score_percentage >= 89.0,
            "primary_focus": None,
            "strategy": None,
            "risk_level": "low",
        }

        if analysis["both_achieved"]:
            analysis["strategy"] = "Maintain current balance - both targets achieved"

        elif analysis["length_achieved"] and not analysis["quality_achieved"]:
            analysis["primary_focus"] = "quality"
            analysis["strategy"] = (
                "Focus on quality improvements - length is already optimal"
            )
            analysis["risk_level"] = "low"

        elif not analysis["length_achieved"] and analysis["quality_achieved"]:
            analysis["primary_focus"] = "length"
            if length_status["adjustment_needed"] == "expand":
                analysis["strategy"] = "Carefully expand content in weak scoring areas"
            else:
                analysis["strategy"] = "Carefully condense while preserving quality"
            analysis["risk_level"] = "medium"

        else:  # Neither achieved
            gap_size = abs(length_status["adjustment_amount"])
            quality_gap = 89.0 - score_percentage

            if quality_gap > 20:  # Large quality gap
                analysis["primary_focus"] = "quality"
                analysis["strategy"] = (
                    "Focus primarily on quality - length will likely improve naturally"
                )
                analysis["risk_level"] = "low"
            elif gap_size > 500:  # Large length gap
                analysis["primary_focus"] = "length"
                analysis["strategy"] = "Address length while monitoring quality impact"
                analysis["risk_level"] = "high"
            else:  # Both gaps manageable
                analysis["primary_focus"] = "balanced"
                analysis["strategy"] = "Address both length and quality simultaneously"
                analysis["risk_level"] = "medium"

        return analysis

    def get_target_word_count_for_improvement(
        self, current_count: int, score_results: Optional[ArticleScoreModel] = None
    ) -> int:
        """
        Calculate optimal target word count for next iteration.

        Args:
            current_count: Current word count
            score_results: Optional scoring results for strategic targeting

        Returns:
            int: Recommended target word count for next iteration
        """
        if self.is_within_range(current_count):
            return current_count  # Already optimal

        if current_count < self.target_min:
            # Calculate expansion target
            shortage = self.target_min - current_count
            if shortage > 1000:
                # Large gap - aim for significant but achievable improvement
                return current_count + min(500, shortage // 2)
            else:
                # Small gap - aim for target range
                return self.target_min

        else:  # current_count > self.target_max
            # Calculate condensation target
            excess = current_count - self.target_max
            if excess > 1000:
                # Large excess - gradual reduction
                return current_count - min(500, excess // 2)
            else:
                # Small excess - aim for target range
                return self.target_max

    def generate_word_length_instructions(
        self,
        word_count: int,
        target_min: int,
        target_max: int,
        score_results: Optional[ArticleScoreModel] = None,
    ) -> str:
        """
        Generate specific word length adjustment instructions based on scoring feedback.

        Args:
            word_count: Current word count
            target_min: Minimum target word count
            target_max: Maximum target word count
            score_results: Current scoring results for targeted guidance

        Returns:
            str: Detailed instructions for word length adjustment
        """
        status = self.get_word_count_status(word_count)
        instructions = []

        instructions.append("WORD LENGTH ADJUSTMENT INSTRUCTIONS")
        instructions.append("=" * 40)
        instructions.append(f"Current: {word_count} words")
        instructions.append(f"Target: {target_min}-{target_max} words")
        instructions.append("")

        if status["adjustment_needed"] == "expand":
            instructions.append(
                f"📈 EXPANSION NEEDED: +{status['adjustment_amount']} words"
            )
            instructions.append(
                "Focus on weak scoring areas to improve both length AND quality:"
            )
            instructions.append("")

            # Get expansion strategies based on scoring weaknesses
            if score_results is not None:
                expansion_strategies = self.suggest_expansion_strategies(score_results)
                instructions.extend(expansion_strategies)
            else:
                instructions.extend(
                    [
                        "GENERAL EXPANSION TECHNIQUES:",
                        "• Add concrete examples and case studies",
                        "• Include relevant data and statistics",
                        "• Expand on implications and consequences",
                        "• Add personal insights and experiences",
                    ]
                )

        elif status["adjustment_needed"] == "condense":
            instructions.append(
                f"📉 CONDENSATION NEEDED: -{status['adjustment_amount']} words"
            )
            instructions.append("Preserve all key insights while removing redundancy:")
            instructions.append("")

            # Get condensation strategies
            condensation_strategies = self.suggest_condensation_strategies("")
            instructions.extend(condensation_strategies)

        else:
            instructions.append("✅ WORD COUNT OPTIMAL")
            instructions.append(
                "Maintain current length while focusing on quality improvements"
            )

        instructions.append("")
        instructions.append("🎯 QUALITY PRESERVATION PRINCIPLES:")
        instructions.append("• Keep all core arguments and evidence")
        instructions.append("• Maintain logical flow and structure")
        instructions.append("• Preserve unique insights and perspectives")
        instructions.append("• Keep examples that strongly support your thesis")

        return "\n".join(instructions)

    def validate_word_count_change(
        self, old_count: int, new_count: int, target_adjustment: str
    ) -> Dict[str, Any]:
        """
        Validate that word count changes align with intended adjustments.

        Args:
            old_count: Previous word count
            new_count: New word count
            target_adjustment: Intended adjustment ('expand', 'condense', or 'maintain')

        Returns:
            Dict with validation results and feedback
        """
        change = new_count - old_count

        validation = {
            "old_count": old_count,
            "new_count": new_count,
            "change": change,
            "target_adjustment": target_adjustment,
            "adjustment_successful": False,
            "feedback": "",
            "recommendation": "",
        }

        if target_adjustment == "expand":
            if change > 0:
                validation["adjustment_successful"] = True
                validation["feedback"] = f"Successfully expanded by {change} words"
            else:
                validation["feedback"] = (
                    f"Failed to expand - actually decreased by {abs(change)} words"
                )
                validation["recommendation"] = (
                    "Review expansion strategies and try again"
                )

        elif target_adjustment == "condense":
            if change < 0:
                validation["adjustment_successful"] = True
                validation["feedback"] = (
                    f"Successfully condensed by {abs(change)} words"
                )
            else:
                validation["feedback"] = (
                    f"Failed to condense - actually increased by {change} words"
                )
                validation["recommendation"] = (
                    "Review condensation strategies and try again"
                )

        else:  # maintain
            if abs(change) <= 50:  # Allow small variations
                validation["adjustment_successful"] = True
                validation["feedback"] = (
                    f"Successfully maintained length (change: {change} words)"
                )
            else:
                validation["feedback"] = f"Unintended length change: {change} words"
                validation["recommendation"] = (
                    "Review changes to maintain target length"
                )

        # Check if new count is within target range
        if self.is_within_range(new_count):
            validation["feedback"] += " - Now within target range!"

        return validation


if __name__ == "__main__":
    # Test the word count manager
    manager = WordCountManager(target_min=2000, target_max=2500)

    print("=== WORD COUNT MANAGER TEST ===")

    # Test word counting
    test_text = "This is a test article with multiple sentences. It should count words accurately."
    word_count = manager.count_words(test_text)
    print(f"\nTest text word count: {word_count}")
    print(f"Text: {test_text}")

    # Test different word count scenarios
    test_counts = [1500, 2250, 3000]

    for count in test_counts:
        print(f"\n--- Testing {count} words ---")
        status = manager.get_word_count_status(count)
        print(f"Within range: {status['within_range']}")
        print(f"Guidance: {status['guidance']}")
        print(f"Priority: {status['priority']}")

        if status["adjustment_needed"]:
            print(
                f"Adjustment needed: {status['adjustment_needed']} by {status['adjustment_amount']} words"
            )

    print("\n" + "=" * 50)
    print("LENGTH OPTIMIZATION PROMPT EXAMPLE:")
    print(manager.get_length_optimization_prompt(1800))
