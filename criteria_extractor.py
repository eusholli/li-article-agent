#!/usr/bin/env python3
"""
Criteria Extractor for LinkedIn Article Generator

This module dynamically extracts and processes scoring criteria from li_article_judge.py
to enable adaptive article generation based on current scoring requirements.
"""

from typing import Dict, List, Tuple, Any
from li_article_judge import SCORING_CRITERIA, ArticleScoreModel


class CriteriaExtractor:
    """
    Dynamically extracts and processes scoring criteria from li_article_judge.py.

    This class provides methods to parse the SCORING_CRITERIA dictionary and convert
    it into formats suitable for article generation and improvement guidance.
    """

    def __init__(self):
        """Initialize the criteria extractor with current scoring criteria."""
        self.criteria = SCORING_CRITERIA
        self._criteria_summary = None
        self._category_weights = None

    def get_criteria_summary(self) -> str:
        """
        Generate a comprehensive summary of scoring criteria for article generation.

        Returns:
            str: Formatted summary of all scoring criteria with weights and requirements
        """
        if self._criteria_summary is None:
            self._criteria_summary = self._build_criteria_summary()
        return self._criteria_summary

    def get_category_weights(self) -> Dict[str, int]:
        """
        Calculate total point weights for each scoring category.

        Returns:
            Dict[str, int]: Category names mapped to their total point values
        """
        if self._category_weights is None:
            self._category_weights = self._calculate_category_weights()
        return self._category_weights

    def get_improvement_guidelines(self, score_results: ArticleScoreModel) -> str:
        """
        Convert scoring feedback into actionable improvement guidelines.

        Args:
            score_results: ArticleScoreModel with detailed scoring breakdown

        Returns:
            str: Specific improvement guidelines based on scoring weaknesses
        """
        guidelines = []
        guidelines.append("=== IMPROVEMENT GUIDELINES ===\n")

        # Analyze category performance
        category_weights = self.get_category_weights()
        weak_categories = []

        for category, results in score_results.category_scores.items():
            category_total = sum(r.score for r in results)
            category_max = category_weights.get(category, 0)
            category_percentage = (
                (category_total / category_max * 100) if category_max > 0 else 0
            )

            if category_percentage < 70:  # Below 70% performance
                weak_categories.append((category, category_percentage, results))

        # Sort by performance (worst first)
        weak_categories.sort(key=lambda x: x[1])

        if weak_categories:
            guidelines.append("PRIORITY IMPROVEMENT AREAS:\n")

            for i, (category, percentage, results) in enumerate(weak_categories[:3], 1):
                guidelines.append(f"{i}. {category} ({percentage:.1f}% performance)")
                guidelines.append(f"   Weight: {category_weights[category]} points")

                # Add specific criterion feedback
                for result in results:
                    if result.score < 3:  # Below average criterion
                        guidelines.append(f"   • {result.criterion}")
                        guidelines.append(f"     Current: {result.score} points")
                        guidelines.append(f"     Issue: {result.reasoning}")
                        guidelines.append(f"     Action: {result.suggestions}")

                guidelines.append("")

        # Add general improvement strategies
        guidelines.append("GENERAL IMPROVEMENT STRATEGIES:")
        guidelines.append("• Focus on the highest-weighted categories first")
        guidelines.append("• Ensure each criterion is explicitly addressed")
        guidelines.append("• Use specific examples and evidence")
        guidelines.append("• Maintain professional LinkedIn tone")
        guidelines.append("• Target 2000-2500 words for optimal length")

        return "\n".join(guidelines)

    def get_high_priority_criteria(self) -> List[Tuple[str, str, int]]:
        """
        Get the highest-weighted criteria for focused improvement.

        Returns:
            List[Tuple[str, str, int]]: (category, question, points) for high-priority criteria
        """
        high_priority = []

        for category, criteria_list in self.criteria.items():
            for criterion in criteria_list:
                points = criterion.get("points", 5)
                if points >= 15:  # High-value criteria
                    high_priority.append((category, criterion["question"], points))

        # Sort by points (highest first)
        high_priority.sort(key=lambda x: x[2], reverse=True)
        return high_priority

    def get_criteria_for_generation(self) -> str:
        """
        Get criteria formatted specifically for article generation prompts.

        Returns:
            str: Criteria formatted for LLM generation prompts
        """
        generation_prompt = []
        generation_prompt.append("SCORING CRITERIA FOR ARTICLE GENERATION:")
        generation_prompt.append("Your article will be evaluated on these criteria:\n")

        category_weights = self.get_category_weights()

        # Sort categories by weight (highest first)
        sorted_categories = sorted(
            category_weights.items(), key=lambda x: x[1], reverse=True
        )

        for category, total_points in sorted_categories:
            generation_prompt.append(f"**{category}** ({total_points} points total):")

            criteria_list = self.criteria[category]
            for criterion in criteria_list:
                points = criterion.get("points", 5)
                question = criterion["question"]

                generation_prompt.append(f"  • ({points} pts) {question}")

                # Add scale guidance for high-value criteria
                if points >= 15:
                    scale = criterion.get("scale", {})
                    if scale:
                        generation_prompt.append(
                            f"    Scale: {scale.get(5, 'Excellent performance')}"
                        )

            generation_prompt.append("")

        generation_prompt.append("OPTIMIZATION PRIORITIES:")
        generation_prompt.append(
            "1. Focus heavily on Strategic Deconstruction & Synthesis (75 points)"
        )
        generation_prompt.append("2. Emphasize First-Order Thinking (45 points)")
        generation_prompt.append(
            "3. Ensure strong engagement and professional authority"
        )
        generation_prompt.append("4. Target 2000-2500 words for optimal length")

        return "\n".join(generation_prompt)

    def _build_criteria_summary(self) -> str:
        """Build comprehensive criteria summary for internal use."""
        summary = []
        summary.append("LINKEDIN ARTICLE SCORING CRITERIA SUMMARY")
        summary.append("=" * 50)

        total_points = sum(self.get_category_weights().values())
        summary.append(f"Total Possible Score: {total_points} points")
        summary.append(f"Target Score: ≥89% ({int(total_points * 0.89)} points)")
        summary.append("")

        # Add category breakdown
        for category, criteria_list in self.criteria.items():
            category_points = sum(c.get("points", 5) for c in criteria_list)
            summary.append(f"{category}: {category_points} points")

            for i, criterion in enumerate(criteria_list, 1):
                points = criterion.get("points", 5)
                question = criterion["question"]
                summary.append(f"  {i}. ({points} pts) {question}")

            summary.append("")

        return "\n".join(summary)

    def _calculate_category_weights(self) -> Dict[str, int]:
        """Calculate total points for each category."""
        weights = {}

        for category, criteria_list in self.criteria.items():
            total_points = sum(
                criterion.get("points", 5) for criterion in criteria_list
            )
            weights[category] = total_points

        return weights

    def get_total_possible_score(self) -> int:
        """Get the total possible score across all criteria."""
        return sum(self.get_category_weights().values())

    def get_target_score(self, target_percentage: float = 89.0) -> int:
        """
        Calculate target score based on percentage.

        Args:
            target_percentage: Target percentage (default 89% for world-class)

        Returns:
            int: Target score in points
        """
        total_possible = self.get_total_possible_score()
        return int(total_possible * (target_percentage / 100))

    def analyze_score_gaps(self, score_results: ArticleScoreModel) -> Dict[str, Any]:
        """
        Analyze gaps between current and target scores.

        Args:
            score_results: Current scoring results

        Returns:
            Dict with gap analysis including priority areas for improvement
        """
        category_weights = self.get_category_weights()
        target_total = self.get_target_score()
        current_total = score_results.total_score

        gap_analysis = {
            "total_gap": target_total - current_total,
            "current_percentage": score_results.percentage,
            "target_percentage": 89.0,
            "category_gaps": {},
            "priority_categories": [],
        }

        # Analyze each category
        for category, results in score_results.category_scores.items():
            category_current = sum(r.score for r in results)
            category_max = category_weights.get(category, 0)
            category_target = int(category_max * 0.89)  # 89% of category max
            category_gap = category_target - category_current

            gap_analysis["category_gaps"][category] = {
                "current": category_current,
                "target": category_target,
                "gap": category_gap,
                "max_possible": category_max,
                "percentage": (
                    (category_current / category_max * 100) if category_max > 0 else 0
                ),
            }

            # Add to priority list if significant gap
            if category_gap > 0:
                gap_analysis["priority_categories"].append(
                    {
                        "category": category,
                        "gap": category_gap,
                        "weight": category_max,
                        "impact_score": category_gap
                        * category_max,  # Gap weighted by category importance
                    }
                )

        # Sort priority categories by impact score
        gap_analysis["priority_categories"].sort(
            key=lambda x: x["impact_score"], reverse=True
        )

        return gap_analysis


# Convenience function for quick access
def get_current_criteria_summary() -> str:
    """Get a quick summary of current scoring criteria."""
    extractor = CriteriaExtractor()
    return extractor.get_criteria_summary()


if __name__ == "__main__":
    # Test the criteria extractor
    extractor = CriteriaExtractor()

    print("=== CRITERIA EXTRACTOR TEST ===")
    print("\nCategory Weights:")
    for category, weight in extractor.get_category_weights().items():
        print(f"  {category}: {weight} points")

    print(f"\nTotal Possible Score: {extractor.get_total_possible_score()}")
    print(f"Target Score (89%): {extractor.get_target_score()}")

    print("\nHigh Priority Criteria:")
    for category, question, points in extractor.get_high_priority_criteria():
        print(f"  {points} pts - {category}: {question[:60]}...")

    print("\n" + "=" * 50)
    print("CRITERIA FOR GENERATION:")
    print(extractor.get_criteria_for_generation())
