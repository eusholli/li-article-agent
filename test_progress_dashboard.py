#!/usr/bin/env python3
"""
Unit tests for Progress Dashboard functionality
"""

import unittest
from progress_dashboard import ProgressDashboard, UserInteractionManager


class TestProgressDashboard(unittest.TestCase):
    """Test cases for ProgressDashboard class."""

    def setUp(self):
        """Set up test fixtures."""
        self.dashboard = ProgressDashboard()

    def test_generate_progress_dashboard_basic(self):
        """Test basic dashboard generation."""
        result = self.dashboard.generate_progress_dashboard(75.0, 89.0)
        self.assertIn("75.0%", result)
        self.assertIn("Strong, but tighten weak areas", result)
        self.assertIn("███████████████", result)  # Progress bar

    def test_generate_progress_dashboard_with_word_count(self):
        """Test dashboard with word count information."""
        result = self.dashboard.generate_progress_dashboard(
            75.0, 89.0, 2100, (2000, 2500)
        )
        self.assertIn("2100 words", result)
        self.assertIn("Within target range", result)

    def test_generate_progress_dashboard_word_count_warnings(self):
        """Test dashboard with word count warnings."""
        # Test under minimum
        result = self.dashboard.generate_progress_dashboard(
            75.0, 89.0, 1800, (2000, 2500)
        )
        self.assertIn("200 words short", result)

        # Test over maximum
        result = self.dashboard.generate_progress_dashboard(
            75.0, 89.0, 2600, (2000, 2500)
        )
        self.assertIn("100 words over", result)

    def test_score_tier_classification(self):
        """Test score tier classification."""
        # World-class
        result = self.dashboard.generate_progress_dashboard(95.0, 89.0)
        self.assertIn("World-class — publish as is", result)

        # Strong
        result = self.dashboard.generate_progress_dashboard(75.0, 89.0)
        self.assertIn("Strong, but tighten weak areas", result)

        # Needs work
        result = self.dashboard.generate_progress_dashboard(60.0, 89.0)
        self.assertIn("Needs restructuring", result)

        # Rework
        result = self.dashboard.generate_progress_dashboard(40.0, 89.0)
        self.assertIn("Rework before publishing", result)

    def test_business_impact_translation(self):
        """Test business impact translation."""
        result = self.dashboard.generate_progress_dashboard(95.0, 89.0)
        self.assertIn("3x engagement", result)

        result = self.dashboard.generate_progress_dashboard(75.0, 89.0)
        self.assertIn("add depth for maximum impact", result)


class TestUserInteractionManager(unittest.TestCase):
    """Test cases for UserInteractionManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.dashboard = ProgressDashboard()
        self.interaction_manager = UserInteractionManager(self.dashboard)

    def test_get_contextual_decision_prompt(self):
        """Test contextual decision prompt generation."""
        prompt = self.interaction_manager.get_contextual_decision_prompt(
            75.0,
            "Focus on strategic analysis",
            ["strategic deconstruction", "authority & credibility"],
        )

        self.assertIn("75.0% complete", prompt)
        self.assertIn("strategic deconstruction", prompt)
        self.assertIn("authority & credibility", prompt)
        self.assertIn("Choose your next action", prompt)
        self.assertIn("1. ✅ Proceed", prompt)
        self.assertIn("2. ✏️  Add specific", prompt)
        self.assertIn("3. 🏁 Finish", prompt)

    def test_improvement_impact_estimation(self):
        """Test improvement impact estimation."""
        # High-impact areas should give higher estimates
        high_impact = self.interaction_manager._estimate_improvement_impact(
            ["first-order thinking", "strategic deconstruction"]
        )
        self.assertGreater(high_impact, 10.0)

        # Low-impact areas should give lower estimates
        low_impact = self.interaction_manager._estimate_improvement_impact(
            ["general improvements"]
        )
        self.assertLess(low_impact, 10.0)


if __name__ == "__main__":
    unittest.main()
