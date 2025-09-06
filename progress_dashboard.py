#!/usr/bin/env python3
"""
Progress Dashboard for LinkedIn Article Generator

Provides user-friendly progress visualization and business impact translation
to replace overwhelming technical output with actionable insights.
"""

from typing import Dict, Any, Optional
import math


class ProgressDashboard:
    """
    Generates visual progress dashboards and translates technical scores
    into business-relevant insights for better user decision making.
    """

    def __init__(self):
        self.score_tiers = {
            89: ("World-class — publish as is", "🎉"),
            72: ("Strong, but tighten weak areas", "💪"),
            56: ("Needs restructuring and sharper insights", "🔧"),
            0: ("Rework before publishing", "⚠️"),
        }

        self.business_impact = {
            "World-class — publish as is": "Will drive 3x engagement and viral potential",
            "Strong, but tighten weak areas": "Good foundation - add depth for maximum impact",
            "Needs restructuring and sharper insights": "Solid draft - needs strategic refinement",
            "Rework before publishing": "Needs fundamental restructuring",
        }

    def generate_progress_dashboard(
        self,
        current_score: float,
        target_score: float = 89.0,
        word_count: Optional[int] = None,
        target_range: Optional[tuple] = None,
        overall_feedback: Optional[str] = None,
    ) -> str:
        """
        Generate a complete progress dashboard with visual elements.

        Args:
            current_score: Current percentage score (0-100)
            target_score: Target percentage score
            word_count: Current word count
            target_range: Tuple of (min_words, max_words)

        Returns:
            Formatted dashboard string
        """
        dashboard_parts = []

        # Header
        dashboard_parts.append("🎯 Article Quality Progress")
        dashboard_parts.append("━" * 50)

        # Current status with tier
        tier_name, emoji = self._get_score_tier(current_score)
        dashboard_parts.append(f"📊 Current Status: {current_score:.1f}% ({tier_name})")
        dashboard_parts.append(f"🎯 Target: ≥{target_score}% (World-class)")

        # Visual progress bar
        progress_bar = self._generate_progress_bar(current_score, target_score)
        dashboard_parts.append(f"📈 Progress: {progress_bar}")

        # Word count if provided
        if word_count and target_range:
            min_words, max_words = target_range
            word_status = self._get_word_count_status(word_count, min_words, max_words)
            dashboard_parts.append(f"📝 Word Count: {word_count} words {word_status}")

        # Business impact
        impact = self.business_impact.get(tier_name, "Analyzing impact...")
        dashboard_parts.append(f"💼 Business Impact: {impact}")

        # Overall feedback if provided
        if overall_feedback:
            dashboard_parts.append("")
            dashboard_parts.append("💬 Overall Feedback:")
            dashboard_parts.append("-" * 30)
            dashboard_parts.append(overall_feedback)

        return "\n".join(dashboard_parts)

    def generate_iteration_preview(
        self,
        current_score: float,
        predicted_improvement: float,
        focus_areas: list,
        time_estimate: str = "2-3 minutes",
    ) -> str:
        """
        Generate preview of what the next iteration will improve.

        Args:
            current_score: Current percentage score
            predicted_improvement: Expected score improvement
            focus_areas: List of areas that will be improved
            time_estimate: Expected time for iteration

        Returns:
            Formatted iteration preview string
        """
        preview_parts = []

        new_score = min(100, current_score + predicted_improvement)
        preview_parts.append(
            f"Your article is {current_score:.1f}% complete. Next iteration will improve:"
        )
        preview_parts.append("")

        preview_parts.append("🎯 Primary Focus Areas:")
        for area in focus_areas[:3]:  # Show top 3
            preview_parts.append(f"  • {area}")
        preview_parts.append("")

        preview_parts.append(
            f"📈 Expected Improvement: +{predicted_improvement:.1f} points ({current_score:.1f}% → {new_score:.1f}%)"
        )
        preview_parts.append(f"⏱️  Time Estimate: {time_estimate}")
        preview_parts.append("")

        # Decision options
        preview_parts.append("Choose your next action:")
        preview_parts.append("  1. ✅ Proceed with these improvements")
        preview_parts.append("  2. ✏️  Add specific instructions for this iteration")
        preview_parts.append("  3. 🏁 Finish with current version")

        return "\n".join(preview_parts)

    def _generate_progress_bar(
        self, current: float, target: float, width: int = 30
    ) -> str:
        """
        Generate a visual progress bar.

        Args:
            current: Current score
            target: Target score
            width: Width of progress bar in characters

        Returns:
            Visual progress bar string
        """
        progress_ratio = min(current / target, 1.0)
        filled_chars = int(progress_ratio * width)
        empty_chars = width - filled_chars

        bar = "█" * filled_chars + "░" * empty_chars
        percentage = min(current / target * 100, 100)

        return f"{bar} {percentage:.1f}%"

    def _get_score_tier(self, score: float) -> tuple[str, str]:
        """
        Get the performance tier and emoji for a score.

        Args:
            score: Percentage score

        Returns:
            Tuple of (tier_name, emoji)
        """
        for threshold, (tier_name, emoji) in self.score_tiers.items():
            if score >= threshold:
                return tier_name, emoji

        return self.score_tiers[0]  # Default to lowest tier

    def _get_word_count_status(
        self, current: int, min_words: int, max_words: int
    ) -> str:
        """
        Get word count status indicator.

        Args:
            current: Current word count
            min_words: Minimum target
            max_words: Maximum target

        Returns:
            Status string with emoji
        """
        if current < min_words:
            shortfall = min_words - current
            return f"(⚠️  {shortfall} words short of minimum)"
        elif current > max_words:
            excess = current - max_words
            return f"(⚠️  {excess} words over maximum)"
        else:
            return "(✅ Within target range)"


class UserInteractionManager:
    """
    Manages contextual user prompts and decision flows
    to replace generic questions with informed guidance.
    """

    def __init__(self, dashboard: ProgressDashboard):
        self.dashboard = dashboard

    def get_contextual_decision_prompt(
        self, current_score: float, improvement_prompt: str, focus_areas: list
    ) -> str:
        """
        Generate a contextual decision prompt based on current state.

        Args:
            current_score: Current percentage score
            improvement_prompt: Judge's improvement guidance
            focus_areas: Key areas needing improvement

        Returns:
            Formatted decision prompt
        """
        # Predict improvement impact (simplified estimation)
        predicted_improvement = self._estimate_improvement_impact(focus_areas)

        preview = self.dashboard.generate_iteration_preview(
            current_score=current_score,
            predicted_improvement=predicted_improvement,
            focus_areas=focus_areas,
        )

        return preview

    def _estimate_improvement_impact(self, focus_areas: list) -> float:
        """
        Estimate the potential improvement impact based on focus areas.

        Args:
            focus_areas: List of improvement areas

        Returns:
            Estimated percentage improvement
        """
        # Simplified impact estimation based on focus area priority
        base_impact = 8.0  # Base improvement

        # Add bonuses for high-impact areas
        high_impact_areas = [
            "first-order thinking",
            "strategic deconstruction",
            "authority & credibility",
            "idea density",
        ]

        bonus = sum(
            2.0
            for area in focus_areas
            if any(high_impact in area.lower() for high_impact in high_impact_areas)
        )

        return min(base_impact + bonus, 15.0)  # Cap at 15 points
