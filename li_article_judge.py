#!/usr/bin/env python3
# li-article-judge.py
"""
LinkedIn Article Quality Judge

This program evaluates LinkedIn articles using AI-powered scoring with heavy emphasis on
first-order thinking and Elon Musk's engineering principles. The scoring system prioritizes
quality of thinking (67% weight) over traditional engagement metrics (33% weight).

Scoring Categories:
- First-Order Thinking (45 points): Breaking down problems to fundamentals
- Musk Engineering Principles (75 points): Question, delete, simplify, accelerate, automate
- Traditional criteria (60 points): Engagement, structure, credibility, clarity, etc.

Usage:
    python li-article-judge.py "Your article text here"
    python li-article-judge.py --file article.txt
    python li-article-judge.py --help
"""

import argparse
import sys
from typing import Dict, List, Optional, Any, Tuple

import dspy
from pydantic import BaseModel, Field, validator
from attachments.dspy import Attachments
from dspy_factory import DspyModelConfig
from context_window_manager import ContextWindowManager, ContextWindowError
from models import ArticleVersion, JudgementModel, ScoreResultModel, ArticleScoreModel
import logging
from word_count_manager import WordCountManager
import random


# ==========================================================================
# SECTION 1: DATA STRUCTURES
# ==========================================================================


class CriterionScoringOutput(BaseModel):
    """
    🎯 PYDANTIC MODEL: DSPy Output for Individual Criterion Scoring

    This Pydantic model defines the structured output format for the ArticleCriterionScorer
    DSPy signature. It ensures that LLM responses contain all required fields with proper
    validation and type safety.

    Benefits of using Pydantic for DSPy outputs:
    - Automatic validation of LLM response structure
    - Type safety and IDE support
    - Clear error messages for invalid responses
    - Eliminates need for manual validation functions
    """

    score: int = Field(..., ge=1, le=5, description="Score from 1-5 for this criterion")
    reasoning: str = Field(
        ...,
        min_length=10,
        description="Detailed explanation of why this score was given",
    )
    suggestions: str = Field(
        ..., min_length=10, description="Specific suggestions for improvement"
    )


class OverallFeedbackOutput(BaseModel):
    """
    💬 PYDANTIC MODEL: DSPy Output for Overall Article Feedback

    This Pydantic model defines the structured output format for the OverallFeedbackGenerator
    DSPy signature. It ensures comprehensive feedback with validated performance tiers.
    """

    overall_feedback: str = Field(
        ...,
        min_length=50,
        description="Comprehensive feedback on the article's strengths and areas for improvement",
    )
    performance_tier: str = Field(
        ...,
        description="Performance tier: World-class, Strong, Needs work, or Rework needed",
    )

    @validator("performance_tier")
    def validate_tier(cls, v):
        """Validate that performance tier is one of the expected values."""
        valid_tiers = [
            "World-class — publish as is",
            "Strong, but tighten weak areas",
            "Needs restructuring and sharper insights",
            "Rework before publishing",
        ]
        # Allow partial matches for flexibility
        if not any(tier_option in v for tier_option in valid_tiers):
            # If no match, still allow it but log a warning
            pass
        return v


class CriterionScore(BaseModel):
    """
    🎯 PYDANTIC MODEL: Individual Criterion Score for Fast Scoring

    This model represents a single criterion's score within the comprehensive scoring system.
    Used by FastLinkedInArticleScorer for structured single-call scoring.
    """

    criterion_id: str = Field(
        ..., description="Criterion identifier (e.g., 'Q1', 'Q2', etc.)"
    )
    category: str = Field(..., description="Category this criterion belongs to")
    question: str = Field(..., description="The criterion question being evaluated")
    raw_score: int = Field(
        ..., ge=1, le=5, description="Raw score from 1-5 for this criterion"
    )
    weighted_score: int = Field(
        ..., description="Weighted score based on criterion point value"
    )
    max_points: int = Field(
        ..., description="Maximum possible points for this criterion"
    )
    reasoning: str = Field(
        ..., min_length=10, description="Detailed explanation of the score"
    )
    suggestions: str = Field(
        ..., min_length=10, description="Specific improvement suggestions"
    )


class CategorySummary(BaseModel):
    """
    📊 PYDANTIC MODEL: Category Summary for Fast Scoring

    This model represents a category-level summary within the comprehensive scoring system.
    """

    category_name: str = Field(..., description="Name of the scoring category")
    total_score: int = Field(..., description="Total points achieved in this category")
    max_score: int = Field(..., description="Maximum possible points for this category")
    percentage: float = Field(..., description="Percentage score for this category")
    key_strengths: str = Field(
        ..., description="Main strengths identified in this category"
    )
    key_weaknesses: str = Field(
        ..., description="Main areas for improvement in this category"
    )


class ComprehensiveArticleScoreOutput(BaseModel):
    """
    🚀 PYDANTIC MODEL: Complete Single-Call Article Scoring Output

    This comprehensive model captures all scoring results in one structured response,
    enabling the FastLinkedInArticleScorer to evaluate all criteria in a single LLM call.

    Benefits:
    - ~95% speed improvement (1 call vs 21+ calls)
    - ~95% cost reduction
    - Better consistency through single context
    - Comprehensive validation ensures completeness
    """

    # Individual criterion scores (all 20+ criteria)
    criterion_scores: List[CriterionScore] = Field(
        ...,
        description="Complete list of scores for all individual criteria",
    )

    # Category-level summaries
    category_summaries: Dict[str, CategorySummary] = Field(
        ..., description="Summary analysis for each scoring category"
    )

    # Overall scoring metrics
    total_score: int = Field(
        ..., description="Total weighted score across all criteria"
    )
    max_score: int = Field(..., description="Maximum possible score (180 points)")
    percentage: float = Field(..., ge=0, le=100, description="Overall percentage score")

    # Performance assessment
    performance_tier: str = Field(..., description="Performance tier classification")
    overall_feedback: str = Field(
        ..., min_length=100, description="Comprehensive article feedback"
    )

    @validator("criterion_scores")
    def validate_criterion_completeness(cls, v):
        """Ensure all expected criteria are present."""
        if len(v) < 20:
            raise ValueError(f"Expected at least 20 criteria, got {len(v)}")
        return v

    @validator("category_summaries")
    def validate_category_completeness(cls, v):
        """Ensure all expected categories are present."""
        expected_categories = {
            "First-Order Thinking",
            "Strategic Deconstruction & Synthesis",
            "Hook & Engagement",
            "Storytelling & Structure",
            "Authority & Credibility",
            "Idea Density & Clarity",
            "Reader Value & Actionability",
            "Call to Connection",
        }
        missing_categories = expected_categories - set(v.keys())
        if missing_categories:
            raise ValueError(f"Missing categories: {missing_categories}")
        return v


class ABComparisonOutput(BaseModel):
    """
    ⚖️ PYDANTIC MODEL: DSPy Output for Article Comparison

    This Pydantic model defines the structured output format for the ABArticleScorer
    DSPy signature. It supports three comparison outcomes: A better, B better, or no difference.
    """

    comparison_result: str = Field(
        ..., description="Comparison result: 'A_better', 'B_better', or 'no_difference'"
    )
    reasoning: str = Field(
        ..., min_length=10, description="Detailed reasoning for the comparison result"
    )

    @validator("comparison_result")
    def validate_result(cls, v):
        """Validate that comparison result is one of the expected values."""
        valid_results = ["A_better", "B_better", "no_difference"]
        if v not in valid_results:
            raise ValueError(f"Must be one of: {valid_results}")
        return v


class ArticleExtractionOutput(BaseModel):
    """
    📄 PYDANTIC MODEL: DSPy Output for File Article Extraction

    This Pydantic model defines the structured output format for the FileArticleExtractor
    DSPy signature. It ensures extracted article text meets minimum length requirements.
    """

    article_text: str = Field(
        ...,
        min_length=50,
        description="Clean, readable article text extracted from the file, ready for analysis",
    )


# ==========================================================================
# SECTION 2: SCORING CRITERIA DEFINITIONS
# ==========================================================================


SCORING_CRITERIA = {
    "First-Order Thinking": [
        {
            "question": "Does the article break down complex problems into fundamental components rather than relying on analogies or existing solutions?",
            "points": 15,
            "scale": {
                1: "Relies heavily on analogies and surface-level comparisons",
                3: "Some attempt to examine fundamentals but inconsistent",
                5: "Consistently breaks problems down to basic principles and rebuilds understanding",
            },
        },
        {
            "question": "Does it challenge conventional wisdom by examining root assumptions and rebuilding from basic principles?",
            "points": 15,
            "scale": {
                1: "Accepts conventional wisdom without question",
                3: "Questions some assumptions but doesn't dig deep",
                5: "Systematically challenges assumptions and rebuilds from first principles",
            },
        },
        {
            "question": "Does it avoid surface-level thinking and instead dig into the 'why' behind commonly accepted ideas?",
            "points": 15,
            "scale": {
                1: "Stays at surface level with obvious observations",
                3: "Some deeper analysis but not consistently applied",
                5: "Consistently probes deeper into root causes and fundamental 'why' questions",
            },
        },
    ],
    "Strategic Deconstruction & Synthesis": [
        {
            "question": "Does it deconstruct a complex system (a market, a company's strategy, a technology) into its fundamental components and incentives?",
            "points": 20,
            "scale": {
                1: "Describes the system at a surface level without dissecting it.",
                3: "Identifies some components but doesn't fully explain their interactions or underlying incentives.",
                5: "Systematically breaks down the system into its core parts and clearly explains how they interact.",
            },
        },
        {
            "question": "Does it synthesize disparate information (e.g., history, financial data, product strategy, quotes) into a single, coherent thesis?",
            "points": 20,
            "scale": {
                1: "Presents information as a list of disconnected facts.",
                3: "Attempts to connect different pieces of information, but the central thesis is weak or unclear.",
                5: "Masterfully weaves together diverse sources into a strong, unified, and memorable argument.",
            },
        },
        {
            "question": "Does it identify second- and third-order effects, explaining the cascading 'so what?' consequences of a core idea or event?",
            "points": 15,
            "scale": {
                1: "Focuses only on the immediate, first-order effects.",
                3: "Mentions some downstream effects but doesn't explore their full implications.",
                5: "Clearly explains the chain reaction of consequences, showing deep understanding of the system's dynamics.",
            },
        },
        {
            "question": "Does it introduce a durable framework or mental model (like 'The Bill Gates Line') that helps explain the system and is transferable to other contexts?",
            "points": 15,
            "scale": {
                1: "Offers opinions without a clear underlying framework.",
                3: "Uses existing frameworks but doesn't introduce a new or refined mental model.",
                5: "Provides a powerful, memorable, and reusable mental model for understanding the topic.",
            },
        },
        {
            "question": "Does it explain the fundamental 'why' behind events, rather than just describing the 'what'?",
            "points": 5,
            "scale": {
                1: "Reports on events without providing deep causal analysis.",
                3: "Offers some explanation for the 'why' but it remains at a surface level.",
                5: "Consistently digs beneath the surface to reveal the core strategic, economic, or historical drivers.",
            },
        },
    ],
    "Hook & Engagement": [
        {
            "question": "Does the opening immediately grab attention with curiosity, emotion, or urgency?",
            "points": 5,
            "scale": {
                1: "Bland opening; no reason to keep reading",
                3: "Somewhat interesting but predictable",
                5: "Strong hook that makes reading irresistible",
            },
        },
        {
            "question": "Does the intro clearly state why this matters to the reader in the first 3 sentences?",
            "points": 5,
            "scale": {
                1: "Relevance is unclear",
                3: "Relevance implied but not explicit",
                5: "Clear, personal relevance to target audience immediately",
            },
        },
    ],
    "Storytelling & Structure": [
        {
            "question": "Is the article structured like a narrative (problem → tension → resolution → takeaway)?",
            "points": 5,
            "scale": {
                1: "Disjointed list of points",
                3: "Some flow, but transitions are weak",
                5: "Smooth arc with a natural flow that keeps readers moving",
            },
        },
        {
            "question": "Are there specific, relatable examples or anecdotes?",
            "points": 5,
            "scale": {
                1: "Generic statements with no real-life grounding",
                3: "Some examples, but not vivid",
                5: "Memorable examples that make points stick",
            },
        },
    ],
    "Authority & Credibility": [
        {
            "question": "Are claims backed by data, research, or credible sources?",
            "points": 5,
            "scale": {
                1: "No evidence given",
                3: "Some supporting info, but patchy",
                5: "Strong, credible evidence throughout",
            },
        },
        {
            "question": "Does the article demonstrate unique experience or perspective?",
            "points": 5,
            "scale": {
                1: "Generic, could be written by anyone",
                3: "Some personal insight but not distinct",
                5: "Clear, lived authority shines through",
            },
        },
    ],
    "Idea Density & Clarity": [
        {
            "question": "Is there one clear, central idea driving the piece?",
            "points": 5,
            "scale": {
                1: "Multiple competing ideas; scattered focus",
                3: "Mostly one theme but diluted by tangents",
                5: "Laser-focused on one strong idea",
            },
        },
        {
            "question": "Is every sentence valuable (no filler or fluff)?",
            "points": 5,
            "scale": {
                1: "Lots of repetition or empty words",
                3: "Mostly relevant with occasional filler",
                5: "Concise, high-value throughout",
            },
        },
    ],
    "Reader Value & Actionability": [
        {
            "question": "Does the reader walk away with practical, actionable insights?",
            "points": 5,
            "scale": {
                1: "Vague advice, nothing to act on",
                3: "Some useful tips but not clearly actionable",
                5: "Concrete steps or takeaways that can be applied immediately",
            },
        },
        {
            "question": "Are lessons transferable beyond the example given?",
            "points": 5,
            "scale": {
                1: "Only relevant in a narrow context",
                3: "Partially transferable",
                5: "Clearly relevant across multiple scenarios",
            },
        },
    ],
    "Call to Connection": [
        {
            "question": "Does it end with a thought-provoking question or reflection prompt?",
            "points": 5,
            "scale": {
                1: "No CTA or a generic 'What do you think?'",
                3: "Somewhat engaging but generic",
                5: "Strong, specific prompt that sparks dialogue",
            },
        },
        {
            "question": "Does it use inclusive, community-building language ('we,' 'us,' shared goals)?",
            "points": 5,
            "scale": {
                1: "Detached, academic tone",
                3: "Some warmth but not consistent",
                5: "Warm, inclusive tone throughout",
            },
        },
    ],
}


# ==========================================================================
# SECTION 3: PYDANTIC VALIDATION
# ==========================================================================

# Note: Manual validation functions have been removed as Pydantic BaseModel classes
# now handle all validation automatically through their field constraints and validators.
# This provides better type safety, clearer error messages, and eliminates the need
# for custom validation logic.


# ==========================================================================
# SECTION 4: DSPY SIGNATURES AND MODULES
# ==========================================================================


class ArticleCriterionScorer(dspy.Signature):
    """Score a LinkedIn article on a specific criterion using a 1-5 scale."""

    article_text = dspy.InputField(
        desc="The full text of the LinkedIn article to evaluate"
    )
    criterion_question = dspy.InputField(desc="The specific scoring criterion question")
    scale_description = dspy.InputField(
        desc="Description of the 1-5 scoring scale for this criterion"
    )

    output: CriterionScoringOutput = dspy.OutputField(
        desc="Structured scoring result with score, reasoning, and suggestions"
    )


class OverallFeedbackGenerator(dspy.Signature):
    """Generate overall feedback and performance tier for a LinkedIn article."""

    article_text = dspy.InputField(desc="The full text of the LinkedIn article")
    total_score = dspy.InputField(desc="Total score achieved out of maximum possible")
    category_breakdown = dspy.InputField(desc="Breakdown of scores by category")

    output: OverallFeedbackOutput = dspy.OutputField(
        desc="Structured feedback with overall assessment and performance tier"
    )


class FileArticleExtractor(dspy.Signature):
    """Extract clean article text from a file attachment for LinkedIn article analysis."""

    file_content: Attachments = dspy.InputField(
        desc="The file containing the LinkedIn article (PDF, DOCX, etc.)"
    )
    output: ArticleExtractionOutput = dspy.OutputField(
        desc="Structured extraction result with clean article text"
    )


class ComprehensiveArticleScorer(dspy.Signature):
    """
    🚀 COMPREHENSIVE SINGLE-CALL ARTICLE SCORER

    Score a LinkedIn article across ALL criteria in one comprehensive evaluation.
    This signature replaces 21+ individual LLM calls with one structured evaluation,
    providing ~95% speed improvement and ~95% cost reduction while maintaining quality.
    Act as a hyper-critical world-class LinkedIn article judge that cares deeply about high quality content.
    """

    article_text = dspy.InputField(
        desc="The full text of the LinkedIn article to evaluate comprehensively"
    )

    scoring_criteria_json = dspy.InputField(
        desc="Complete scoring criteria structure with all categories, questions, point values, and scales in JSON format"
    )

    output: ComprehensiveArticleScoreOutput = dspy.OutputField(
        desc="""Complete scoring results for ALL criteria with structured breakdown.

CRITICAL REQUIREMENTS:
1. Score ALL 20+ individual criteria (Q1-Q20+) with scores 1-5
2. Provide detailed reasoning and suggestions for each criterion
3. Calculate weighted scores based on point values (5-20 points per criterion)
4. Generate category summaries for all 8 categories
5. Provide comprehensive overall feedback and performance tier
6. Ensure total consistency across all scoring components

SCORING GUIDELINES:
- Use the full 1-5 scale for each criterion
- Consider criterion relationships and consistency
- Provide specific, actionable suggestions
- Focus on first-order thinking and strategic analysis
- Weight higher-point criteria appropriately in reasoning

OUTPUT STRUCTURE VALIDATION:
- criterion_scores: List of exactly 20+ CriterionScore objects
- category_summaries: Dict with all 8 category summaries
- total_score: Sum of all weighted criterion scores
- percentage: (total_score / 180) * 100
- performance_tier: Based on percentage thresholds
- overall_feedback: Comprehensive analysis (100+ characters)"""
    )


class ABArticleScorer(dspy.Signature):
    """
    Compare two versions of a LinkedIn article and determine the better one based on the provided scoring criteria.
    Supports three outcomes: A better, B better, or no real difference.

    CRITICAL INSTRUCTIONS:
    - Compare the two articles comprehensively using the scoring criteria
    - Return EXACTLY ONE of these three values in comparison_result:
      * "A_better" - if Article A is clearly better than Article B
      * "B_better" - if Article B is clearly better than Article A
      * "no_difference" - if there is no real difference between the articles
    - Only use "no_difference" when the articles are truly equivalent in quality
    - Provide detailed reasoning explaining your choice
    """

    article_a = dspy.InputField(
        desc="The first version of the LinkedIn article to evaluate"
    )

    article_b = dspy.InputField(
        desc="The second version of the LinkedIn article to evaluate"
    )

    scoring_criteria_json = dspy.InputField(
        desc="The scoring criteria to use for evaluation in JSON format"
    )

    output: ABComparisonOutput = dspy.OutputField(
        desc="Structured comparison result with result type and reasoning. Must use exactly one of: 'A_better', 'B_better', or 'no_difference'"
    )


class LinkedInArticleScorer(dspy.Module):
    """Complete LinkedIn article scoring system using DSPy."""

    def __init__(self, models: Dict[str, DspyModelConfig]):
        """
        Initialize the LinkedIn Article Scorer.

        Args:
            model_name: Optional model name for scoring components
        """
        super().__init__()

        self.models = models
        self.context_manager = ContextWindowManager(models["judge"])
        self.criterion_scorer = dspy.ChainOfThought(ArticleCriterionScorer)
        self.feedback_generator = dspy.ChainOfThought(OverallFeedbackGenerator)

    def forward(self, article_text: str) -> dspy.Prediction:
        """Score an article across all criteria and generate comprehensive feedback.

        Returns:
            dspy.Prediction object containing ArticleScoreModel as output field
        """

        category_scores = {}
        total_score = 0
        max_score = 0
        criterion_counter = 1  # Counter for generating Q1, Q2, etc.

        print("📊 Analyzing article across all criteria...")

        # Score each category and criterion
        for category_name, criteria in SCORING_CRITERIA.items():
            print(f"  • Evaluating {category_name}...")
            category_results = []

            for criterion in criteria:
                # Get the point value for this criterion (default to 5 if not specified)
                criterion_points = criterion.get("points", 5)
                max_score += criterion_points

                # Generate criterion ID dynamically
                criterion_id = f"Q{criterion_counter}"
                criterion_counter += 1

                # Format scale description
                scale_desc = "\n".join(
                    [f"{score}: {desc}" for score, desc in criterion["scale"].items()]
                )

                try:
                    with dspy.context(lm=self.models["judge"].dspy_lm):
                        result = self.criterion_scorer(
                            article_text=article_text,
                            criterion_question=criterion["question"],
                            scale_description=scale_desc,
                        )
                except Exception as e:
                    error_string = (
                        f"⚠️ Scoring '{criterion["question"]}' failed ({str(e)})"
                    )
                    print(error_string)
                    logging.error(error_string)

                    # Create a fallback result with Pydantic structure
                    class FallbackResult:
                        def __init__(self):
                            self.output = CriterionScoringOutput(
                                score=0,  # Default zero score
                                reasoning=f"Unable to analyze this criterion due to response format issues. Criterion: {criterion['question'][:100]}...",
                                suggestions="Try scoring criterion again.",
                            )

                    result = FallbackResult()

                # Parse and validate score from Pydantic output
                try:
                    raw_score = int(result.output.score)
                    raw_score = max(1, min(5, raw_score))  # Clamp to 1-5 range
                except (ValueError, AttributeError):
                    raw_score = 3  # Default to middle score if parsing fails

                # Calculate weighted score based on criterion points
                weighted_score = (raw_score * criterion_points) // 5
                total_score += weighted_score

                score_result = ScoreResultModel(
                    criterion=f"{criterion_id}: {criterion['question']}",
                    score=weighted_score,
                    reasoning=str(result.output.reasoning),
                    suggestions=str(result.output.suggestions),
                )
                category_results.append(score_result)

            category_scores[category_name] = category_results

        # Calculate percentage and determine performance tier
        percentage = (total_score / max_score) * 100

        if percentage >= 89:
            tier = "World-class — publish as is"
        elif percentage >= 72:
            tier = "Strong, but tighten weak areas"
        elif percentage >= 56:
            tier = "Needs restructuring and sharper insights"
        else:
            tier = "Rework before publishing"

        print("🤖 Generating overall feedback...")

        # Generate overall feedback
        category_breakdown_parts = []
        for cat, results in category_scores.items():
            category_total = sum(r.score for r in results)
            # Calculate category max based on actual point values
            category_max = sum(
                SCORING_CRITERIA[cat][i].get("points", 5) for i in range(len(results))
            )
            category_breakdown_parts.append(f"{cat}: {category_total}/{category_max}")

        category_breakdown = "\n".join(category_breakdown_parts)

        with dspy.context(lm=self.models["judge"].dspy_lm):
            feedback_result = self.feedback_generator(
                article_text=article_text,
                total_score=f"{total_score}/{max_score}",
                category_breakdown=category_breakdown,
            )

        score_model = ArticleScoreModel(
            total_score=total_score,
            max_score=max_score,
            percentage=percentage,
            category_scores=category_scores,
            overall_feedback=feedback_result.output.overall_feedback,
            performance_tier=tier,
            word_count=None,
        )

        return dspy.Prediction(output=score_model)


def prepare_criteria_json() -> str:
    """
    Prepare the scoring criteria as a JSON string for the LLM.

    Returns:
        JSON string containing all criteria with structure and weights
    """
    import json

    # Create a structured representation of criteria for the LLM
    criteria_structure = {}
    criterion_counter = 1

    for category_name, criteria in SCORING_CRITERIA.items():
        criteria_structure[category_name] = {
            "criteria": [],
            "total_points": sum(c.get("points", 5) for c in criteria),
        }

        for criterion in criteria:
            criterion_data = {
                "id": f"Q{criterion_counter}",
                "question": criterion["question"],
                "points": criterion.get("points", 5),
                "scale": criterion["scale"],
            }
            criteria_structure[category_name]["criteria"].append(criterion_data)
            criterion_counter += 1

    return json.dumps(criteria_structure, indent=2)


class ComprehensiveLinkedInArticleJudge(dspy.Module):
    """
    🎯 COMPREHENSIVE LINKEDIN ARTICLE JUDGE - Complete Judging with Analysis

    This judge encapsulates all judging logic including scoring, requirements checking,
    and improvement analysis. It returns a complete JudgementModel with ready-to-use
    improvement prompts, providing clean separation of concerns.

    Key Benefits:
    - Encapsulates all improvement analysis logic
    - Configuration-driven decision making
    - Ready-to-use improvement prompts
    - Clean interface for generator integration
    - Supports different judge implementations
    """

    def __init__(
        self,
        models: Dict[str, DspyModelConfig],
        min_length: int,
        max_length: int,
        passing_score_percentage: float,
    ):
        """
        Initialize the Comprehensive LinkedIn Article Judge.

        Args:
            models: Dictionary of model configurations for different components
            min_length: Minimum acceptable word count
            max_length: Maximum acceptable word count
            passing_score_percentage: Minimum percentage score to pass
        """
        super().__init__()

        self.models = models
        self.min_length = min_length
        self.max_length = max_length
        self.passing_score_percentage = passing_score_percentage

        # Initialize the underlying fast scorer
        self.scorer = FastLinkedInArticleScorer(models)

        # AB judge
        self.best_version = dspy.ChainOfThought(ABArticleScorer)

        self.criteria_extractor = CriteriaExtractor()
        self.word_count_manager = WordCountManager(min_length, max_length)

    def compare_versions(
        self, article_versions: List[ArticleVersion]
    ) -> Optional[ArticleVersion]:
        """
        Judge an article and return complete judgement with improvement guidance.

        Args:
            versions: List of ArticleVersion objects

        Returns:
            ArticleVersion to return or None if to continue judging latest version
        """

        # Extract the latest and previous versions
        if len(article_versions) < 2:
            return None  # Need at least two versions to compare

        latest_version = article_versions[-1]
        previous_version = article_versions[-2]

        # randomly choose one of the versions to be article_a and the other to be article_b

        if random.choice([True, False]):
            article_a = latest_version.content
            article_b = previous_version.content
            latest_is_a = True
        else:
            article_a = previous_version.content
            article_b = latest_version.content
            latest_is_a = False

        scoring_criteria = prepare_criteria_json()

        judge_result = self.best_version(
            article_a=article_a,
            article_b=article_b,
            scoring_criteria_json=scoring_criteria,
        )

        # Extract comparison result from the new structured output
        comparison_result = judge_result.output.comparison_result
        reasoning = judge_result.output.reasoning

        # Determine which version is better based on the comparison result
        if comparison_result == "A_better":
            if latest_is_a:
                latest_best = True
            else:
                latest_best = False
        elif comparison_result == "B_better":
            if latest_is_a:
                latest_best = False
            else:
                latest_best = True
        elif comparison_result == "no_difference":
            # No real difference - keep previous version as requested
            latest_best = False
        else:
            # Fallback to previous version if unexpected result
            latest_best = False

        if latest_best:
            overall_feedback = [
                "The latest version is better for the following reasons."
            ]
            overall_feedback.append(reasoning)
            latest_version.judgement.overall_feedback = "\n".join(overall_feedback)
            return None  # Keep the latest version
        else:
            # Previous article is best OR no real difference, keep previous version
            if comparison_result == "no_difference":
                overall_feedback = [
                    "No real difference between versions - keeping previous version as requested."
                ]
            else:
                overall_feedback = [
                    "The previous version is better for the following reasons."
                ]
            overall_feedback.append(reasoning)
            overall_feedback.append("We are keeping the previous version.")

            judgement = previous_version.judgement
            judgement.overall_feedback = "\n".join(overall_feedback)
            judgement.meets_requirements = True

            latest_version.content = previous_version.content
            latest_version.judgement = judgement
            latest_version.context = previous_version.context

            return latest_version

    def forward(self, article_versions: List[ArticleVersion]) -> dspy.Prediction:
        """
        Judge an article and return complete judgement with improvement guidance.

        Args:
            versions: List of ArticleVersion objects

        Returns:
            dspy.Prediction object containing JudgementModel as output field
        """
        # Get the latest article version
        latest_version = article_versions[-1]
        article_text = latest_version.content

        # Count words and check length requirements
        word_count = self.word_count_manager.count_words(article_text)
        length_status = self.word_count_manager.get_word_count_status(word_count)
        length_achieved = length_status["within_range"]

        if not length_achieved:
            improvement_prompt = self.criteria_extractor.get_criteria_for_generation()

            # Create the judgement model
            length_judgement = JudgementModel(
                total_score=0,
                max_score=100,
                percentage=0.0,
                performance_tier="Pending",
                word_count=word_count,
                meets_requirements=False,
                improvement_prompt=improvement_prompt,
                focus_areas="Pending Judging while word length is acceptable.",
                overall_feedback="Pending Judging while word length is acceptable.",
            )

            latest_version.judgement = length_judgement
            return dspy.Prediction(output=latest_version)

        # Proceed with full scoring if length is acceptable

        # First check if the previous version was better
        judge_previous = self.compare_versions(article_versions)
        if judge_previous:
            return dspy.Prediction(output=judge_previous)

        # Latest version is best, proceed to score it
        score_prediction = self.scorer(article_text)
        score_results = score_prediction.output

        # Check if both targets are achieved
        quality_achieved = score_results.percentage >= self.passing_score_percentage
        # meets_requirements = quality_achieved and length_achieved

        # Generate improvement analysis if needed
        if quality_achieved:
            improvement_prompt = (
                "Article meets all requirements. No improvements needed."
            )
            focus_areas = "None - targets achieved"
        else:
            improvement_analysis = self._analyze_improvement_needs(
                score_results, article_text, word_count
            )
            improvement_prompt = improvement_analysis["detailed_feedback"]
            focus_areas = improvement_analysis["focus_summary"]

        # Create the judgement model
        judgement = latest_version.judgement

        judgement.total_score = score_results.total_score
        judgement.max_score = score_results.max_score
        judgement.percentage = score_results.percentage
        judgement.performance_tier = score_results.performance_tier
        judgement.word_count = word_count
        judgement.meets_requirements = quality_achieved
        judgement.improvement_prompt = improvement_prompt
        judgement.focus_areas = focus_areas
        # Append to overall feedback with scoring results
        judgement.overall_feedback = (
            (judgement.overall_feedback + "\n\n" + score_results.overall_feedback)
            if judgement.overall_feedback
            else score_results.overall_feedback
        )

        latest_version.judgement = judgement
        return dspy.Prediction(output=latest_version)

    def _analyze_improvement_needs(
        self, score_results: ArticleScoreModel, current_article: str, word_count: int
    ) -> Dict[str, Any]:
        """Analyze what improvements are needed based on scoring results."""

        # Get improvement guidelines from criteria extractor
        improvement_guidelines = self.criteria_extractor.get_improvement_guidelines(
            score_results
        )

        # Get gap analysis
        gap_analysis = self.criteria_extractor.analyze_score_gaps(
            score_results, self.passing_score_percentage
        )

        # Get word count analysis
        length_analysis = self.word_count_manager.analyze_length_vs_quality_tradeoffs(
            word_count, score_results.percentage
        )

        # Determine focus areas
        priority_categories = gap_analysis["priority_categories"][
            :3
        ]  # Top 3 priority areas
        focus_areas = [cat["category"] for cat in priority_categories]

        focus_summary = (
            ", ".join(focus_areas) if focus_areas else "General quality improvements"
        )

        # Generate detailed feedback
        detailed_feedback = self._generate_detailed_feedback(
            score_results,
            gap_analysis,
            length_analysis,
            improvement_guidelines,
            word_count,
        )

        return {
            "score_results": score_results,
            "gap_analysis": gap_analysis,
            "length_analysis": length_analysis,
            "focus_areas": focus_areas,
            "focus_summary": focus_summary,
            "detailed_feedback": detailed_feedback,
            "improvement_guidelines": improvement_guidelines,
        }

    def _generate_detailed_feedback(
        self,
        score_results: ArticleScoreModel,
        gap_analysis: Dict[str, Any],
        length_analysis: Dict[str, Any],
        improvement_guidelines: str,
        word_count: int,
    ) -> str:
        """Generate comprehensive feedback for improvement prioritized by scoring results."""

        feedback_parts = []

        # Current performance summary
        feedback_parts.append("CURRENT PERFORMANCE ANALYSIS:")
        feedback_parts.append(
            f"Score: {score_results.total_score}/{self.criteria_extractor.get_total_possible_score()} ({score_results.percentage:.1f}%)"
        )
        feedback_parts.append(f"Gap to target: {gap_analysis['total_gap']} points")
        feedback_parts.append("")

        # Priority improvement areas based on scoring gaps
        if gap_analysis["priority_categories"]:
            feedback_parts.append("🎯 TOP PRIORITY IMPROVEMENTS (Ordered by Impact):")
            for i, cat_info in enumerate(gap_analysis["priority_categories"][:3], 1):
                category = cat_info["category"]
                gap = cat_info["gap"]
                weight = cat_info["weight"]
                potential_gain = cat_info.get("potential_gain", gap)
                feedback_parts.append(
                    f"{i}. {category}: +{gap} points needed (weight: {weight}, potential gain: +{potential_gain})"
                )
            feedback_parts.append("")

        # Detailed word count strategy with category-specific guidance
        # Use the actual word count passed to this method
        length_status = self.word_count_manager.get_word_count_status(word_count)

        feedback_parts.append("📝 WORD COUNT STRATEGY WITH CATEGORY-SPECIFIC GUIDANCE:")
        feedback_parts.append(
            f"Current: {word_count} words | Target: {self.min_length}-{self.max_length} words"
        )
        feedback_parts.append(
            f"Within Range: {length_status['within_range']} | Strategy: {length_analysis['strategy']}"
        )
        feedback_parts.append("")

        # Generate category-specific expansion/reduction recommendations
        priority_categories = [
            cat["category"] for cat in gap_analysis["priority_categories"][:3]
        ]

        if word_count < self.min_length:
            feedback_parts.append(
                "🔍 EXPANSION RECOMMENDATIONS (Prioritized by Scoring Gaps):"
            )
            words_needed = self.min_length - word_count
            feedback_parts.append(
                f"Need +{words_needed} words minimum. Focus expansion on:"
            )

            for i, category in enumerate(priority_categories, 1):
                category_score = sum(
                    r.score for r in score_results.category_scores[category]
                )
                category_max = sum(
                    SCORING_CRITERIA[category][j].get("points", 5)
                    for j in range(len(score_results.category_scores[category]))
                )
                category_percentage = (
                    (category_score / category_max) * 100 if category_max > 0 else 0
                )

                # Suggest word allocation based on category priority and current performance
                if category_percentage < 70:  # Low performing category
                    suggested_words = max(
                        100, words_needed // (len(priority_categories) - i + 1)
                    )
                    feedback_parts.append(
                        f"  {i}. {category} (+{suggested_words} words): Low performance ({category_percentage:.1f}%)"
                    )
                    feedback_parts.append(
                        f"     Focus: Add detailed examples, deeper analysis, specific evidence"
                    )
                elif category_percentage < 85:  # Medium performing category
                    suggested_words = max(
                        50, words_needed // (len(priority_categories) * 2)
                    )
                    feedback_parts.append(
                        f"  {i}. {category} (+{suggested_words} words): Moderate performance ({category_percentage:.1f}%)"
                    )
                    feedback_parts.append(
                        f"     Focus: Strengthen weak criteria, add supporting details"
                    )

        elif word_count > self.max_length:
            feedback_parts.append(
                "✂️ REDUCTION RECOMMENDATIONS (Preserve High-Scoring Content):"
            )
            words_to_cut = word_count - self.max_length
            feedback_parts.append(
                f"Need -{words_to_cut} words. Reduce from lowest-performing areas:"
            )

            # Sort categories by performance (lowest first for reduction)
            category_performance = []
            for (
                category_name,
                category_results,
            ) in score_results.category_scores.items():
                category_score = sum(r.score for r in category_results)
                category_max = sum(
                    SCORING_CRITERIA[category_name][j].get("points", 5)
                    for j in range(len(category_results))
                )
                category_percentage = (
                    (category_score / category_max) * 100 if category_max > 0 else 0
                )
                category_performance.append(
                    (category_name, category_percentage, category_score)
                )

            category_performance.sort(
                key=lambda x: x[1]
            )  # Sort by percentage (lowest first)

            for i, (category, percentage, score) in enumerate(category_performance[:3]):
                suggested_reduction = max(20, words_to_cut // 3)
                feedback_parts.append(
                    f"  {i+1}. {category} (-{suggested_reduction} words): {percentage:.1f}% performance"
                )
                feedback_parts.append(
                    f"     Focus: Remove redundancy, tighten weak arguments, eliminate filler"
                )

        feedback_parts.append("")

        # Detailed category-specific feedback prioritized by scoring gaps
        feedback_parts.append(
            "🔍 DETAILED IMPROVEMENT FEEDBACK (Prioritized by Scoring Impact):"
        )
        feedback_parts.append("-" * 60)

        # Process categories in priority order first, then remaining categories
        processed_categories = set()

        # First, process priority categories
        for cat_info in gap_analysis["priority_categories"][:3]:
            category_name = cat_info["category"]
            if category_name in score_results.category_scores:
                self._add_category_feedback(
                    feedback_parts,
                    category_name,
                    score_results.category_scores[category_name],
                    priority=True,
                )
                processed_categories.add(category_name)

        # Then process remaining categories
        for category_name, category_results in score_results.category_scores.items():
            if category_name not in processed_categories:
                self._add_category_feedback(
                    feedback_parts, category_name, category_results, priority=False
                )

        # Strategic improvement guidelines
        feedback_parts.append("🎯 STRATEGIC IMPROVEMENT GUIDELINES:")
        feedback_parts.append(improvement_guidelines)

        return "\n".join(feedback_parts)

    def _add_category_feedback(
        self,
        feedback_parts: List[str],
        category_name: str,
        category_results: List,
        priority: bool = False,
    ):
        """Add category-specific feedback to the improvement prompt."""

        # Calculate category score and percentage
        category_score = sum(r.score for r in category_results)
        category_max = sum(
            SCORING_CRITERIA[category_name][i].get("points", 5)
            for i in range(len(category_results))
        )
        category_percentage = (
            (category_score / category_max) * 100 if category_max > 0 else 0
        )

        priority_indicator = "🔥 PRIORITY: " if priority else ""
        feedback_parts.append(
            f"\n{priority_indicator}📁 {category_name} ({category_score}/{category_max} - {category_percentage:.1f}%):"
        )

        # Include suggestions from low-scoring criteria in this category
        has_improvements = False
        for result in category_results:
            # Extract criterion points from the original criteria
            criterion_index = None
            for i, criterion in enumerate(SCORING_CRITERIA[category_name]):
                if criterion["question"] in result.criterion:
                    criterion_index = i
                    break

            if criterion_index is not None:
                criterion_points = SCORING_CRITERIA[category_name][criterion_index].get(
                    "points", 5
                )
                # Calculate raw score (1-5) from weighted score
                raw_score = (
                    (result.score * 5) // criterion_points
                    if criterion_points > 0
                    else 3
                )

                # Include feedback for criteria scoring 3 or below (needs improvement)
                # For priority categories, also include score 4 criteria
                threshold = 4 if priority else 3
                if raw_score <= threshold:
                    has_improvements = True
                    urgency = (
                        "🚨 CRITICAL"
                        if raw_score <= 2
                        else "⚠️ NEEDS WORK" if raw_score <= 3 else "💡 ENHANCE"
                    )
                    feedback_parts.append(f"  {urgency}: {result.criterion}")
                    feedback_parts.append(
                        f"    Current: {result.score}/{criterion_points} points (raw score: {raw_score}/5)"
                    )
                    feedback_parts.append(f"    Issue: {result.reasoning}")
                    feedback_parts.append(f"    Action: {result.suggestions}")
                    feedback_parts.append("")

        if not has_improvements:
            feedback_parts.append(
                "  ✅ This category is performing well - maintain current approach"
            )
            feedback_parts.append("")


class FastLinkedInArticleScorer(dspy.Module):
    """
    🚀 FAST LINKEDIN ARTICLE SCORER - Single LLM Call Implementation

    This optimized scorer evaluates all criteria in ONE comprehensive LLM call,
    providing ~95% speed improvement and ~95% cost reduction compared to the
    original LinkedInArticleScorer while maintaining scoring quality.

    Key Benefits:
    - 1 LLM call vs 21+ calls (original implementation)
    - Massive cost reduction for API usage
    - Better consistency through single evaluation context
    - Comprehensive Pydantic validation ensures completeness
    - Maintains backward compatibility with ArticleScoreModel
    """

    def __init__(self, models: Dict[str, DspyModelConfig]):
        """
        Initialize the Fast LinkedIn Article Scorer.

        Args:
            models: Dictionary of model configurations for different components
        """
        super().__init__()

        self.models = models
        self.context_manager = ContextWindowManager(models["judge"])
        self.comprehensive_scorer = dspy.ChainOfThought(ComprehensiveArticleScorer)

    def _prepare_criteria_json(self) -> str:
        """
        Prepare the scoring criteria as a JSON string for the LLM.

        Returns:
            JSON string containing all criteria with structure and weights
        """
        import json

        # Create a structured representation of criteria for the LLM
        criteria_structure = {}
        criterion_counter = 1

        for category_name, criteria in SCORING_CRITERIA.items():
            criteria_structure[category_name] = {
                "criteria": [],
                "total_points": sum(c.get("points", 5) for c in criteria),
            }

            for criterion in criteria:
                criterion_data = {
                    "id": f"Q{criterion_counter}",
                    "question": criterion["question"],
                    "points": criterion.get("points", 5),
                    "scale": criterion["scale"],
                }
                criteria_structure[category_name]["criteria"].append(criterion_data)
                criterion_counter += 1

        return json.dumps(criteria_structure, indent=2)

    def _convert_to_legacy_format(
        self, comprehensive_result: ComprehensiveArticleScoreOutput
    ) -> ArticleScoreModel:
        """
        Convert the comprehensive scoring result to the legacy ArticleScoreModel format
        for backward compatibility.

        Args:
            comprehensive_result: The comprehensive scoring output from the fast scorer

        Returns:
            ArticleScoreModel compatible with existing interfaces
        """
        # Group criterion scores by category for legacy format
        category_scores = {}

        for category_name in SCORING_CRITERIA.keys():
            category_results = []

            # Find all criteria for this category
            for criterion_score in comprehensive_result.criterion_scores:
                if criterion_score.category == category_name:
                    # Convert to legacy ScoreResultModel format
                    legacy_result = ScoreResultModel(
                        criterion=f"{criterion_score.criterion_id}: {criterion_score.question}",
                        score=criterion_score.weighted_score,
                        reasoning=criterion_score.reasoning,
                        suggestions=criterion_score.suggestions,
                    )
                    category_results.append(legacy_result)

            category_scores[category_name] = category_results

        return ArticleScoreModel(
            total_score=comprehensive_result.total_score,
            max_score=comprehensive_result.max_score,
            percentage=comprehensive_result.percentage,
            category_scores=category_scores,
            overall_feedback=comprehensive_result.overall_feedback,
            performance_tier=comprehensive_result.performance_tier,
            word_count=None,
        )

    def _validate_and_fix_result(
        self, result: ComprehensiveArticleScoreOutput
    ) -> ComprehensiveArticleScoreOutput:
        """
        Validate the comprehensive result and fix any issues to ensure completeness.

        Args:
            result: The raw comprehensive scoring result

        Returns:
            Validated and potentially corrected result
        """
        # Ensure we have all expected criteria
        expected_criteria_count = sum(
            len(criteria) for criteria in SCORING_CRITERIA.values()
        )

        if len(result.criterion_scores) < expected_criteria_count:
            print(
                f"⚠️ Warning: Expected {expected_criteria_count} criteria, got {len(result.criterion_scores)}"
            )

            # Create missing criteria with default scores
            existing_ids = {cs.criterion_id for cs in result.criterion_scores}
            criterion_counter = 1

            for category_name, criteria in SCORING_CRITERIA.items():
                for criterion in criteria:
                    criterion_id = f"Q{criterion_counter}"
                    criterion_counter += 1

                    if criterion_id not in existing_ids:
                        # Add missing criterion with default score
                        missing_criterion = CriterionScore(
                            criterion_id=criterion_id,
                            category=category_name,
                            question=criterion["question"],
                            raw_score=3,  # Default middle score
                            weighted_score=(3 * criterion.get("points", 5)) // 5,
                            max_points=criterion.get("points", 5),
                            reasoning="Default score applied due to missing evaluation",
                            suggestions="Re-evaluate this criterion for more accurate scoring",
                        )
                        result.criterion_scores.append(missing_criterion)

        # Recalculate totals to ensure consistency
        total_score = sum(cs.weighted_score for cs in result.criterion_scores)
        max_score = sum(cs.max_points for cs in result.criterion_scores)
        percentage = (total_score / max_score) * 100 if max_score > 0 else 0

        # Update the result with corrected values
        result.total_score = total_score
        result.max_score = max_score
        result.percentage = percentage

        # Ensure performance tier is set correctly
        if percentage >= 89:
            result.performance_tier = "World-class — publish as is"
        elif percentage >= 72:
            result.performance_tier = "Strong, but tighten weak areas"
        elif percentage >= 56:
            result.performance_tier = "Needs restructuring and sharper insights"
        else:
            result.performance_tier = "Rework before publishing"

        return result

    def forward(self, article_text: str) -> dspy.Prediction:
        """
        Score an article using the fast single-call approach.

        Args:
            article_text: The article text to score

        Returns:
            dspy.Prediction object containing ArticleScoreModel as output field
        """
        print(
            "🚀 Fast scoring: Analyzing article with single comprehensive evaluation..."
        )

        # Prepare criteria JSON for the LLM
        criteria_json = self._prepare_criteria_json()

        try:
            # Make the single comprehensive scoring call
            with dspy.context(lm=self.models["judge"].dspy_lm):
                result = self.comprehensive_scorer(
                    article_text=article_text, scoring_criteria_json=criteria_json
                )

            # Validate and fix the result
            validated_result = self._validate_and_fix_result(result.output)

            # Convert to legacy format for backward compatibility
            legacy_result = self._convert_to_legacy_format(validated_result)

            print(
                f"✅ Fast scoring complete: {legacy_result.total_score}/{legacy_result.max_score} ({legacy_result.percentage:.1f}%)"
            )

            return dspy.Prediction(output=legacy_result)

        except Exception as e:
            print(f"⚠️ Fast scoring failed, falling back to original method: {str(e)}")
            logging.error(f"FastLinkedInArticleScorer failed: {str(e)}")

            # Fallback to original scorer if fast scoring fails
            original_scorer = LinkedInArticleScorer(self.models)
            result = original_scorer(article_text)
            return dspy.Prediction(output=result.output)


# ==========================================================================
# SECTION 5: SCORING AND REPORTING FUNCTIONS
# ==========================================================================


def print_score_report(score) -> None:
    """
    Print a formatted report of the article scoring results.

    Args:
        score: The scoring model object (JudgementModel or ArticleScoreModel)
    """
    print("\n" + "=" * 80)
    print("📋 LINKEDIN ARTICLE QUALITY SCORE REPORT")
    print("=" * 80)
    print(
        f"🎯 Overall Score: {score.total_score}/{score.max_score} ({score.percentage:.1f}%)"
    )
    print(f"🏆 Performance Tier: {score.performance_tier}")

    # Display word count if available
    if hasattr(score, "word_count") and score.word_count is not None:
        print(f"📝 Word Count: {score.word_count} words")
    print()

    # Check if this is the old ArticleScoreModel with category_scores
    if hasattr(score, "category_scores"):
        print("📊 CATEGORY BREAKDOWN:")
        print("-" * 40)
        for category, results in score.category_scores.items():
            category_score = sum(r.score for r in results)
            # Calculate category max based on actual point values
            category_max = sum(
                SCORING_CRITERIA[category][i].get("points", 5)
                for i in range(len(results))
            )
            print(f"📁 {category}: {category_score}/{category_max}")

            for i, result in enumerate(results):
                criterion_points = SCORING_CRITERIA[category][i].get("points", 5)
                print(f"  • {result.criterion}")
                print(f"    Score: {result.score}/{criterion_points}")
                print(f"    Reasoning: {result.reasoning}")
                if result.suggestions:
                    print(f"    💡 Suggestions: {result.suggestions}")
                print()
    else:
        # For simplified JudgementModel, show basic category breakdown
        print("📊 CATEGORY SUMMARY:")
        print("-" * 40)
        total_possible = 180  # Known total from criteria
        for category_name, criteria in SCORING_CRITERIA.items():
            category_max = sum(c.get("points", 5) for c in criteria)
            # Estimate category score proportionally
            estimated_score = int((score.total_score / total_possible) * category_max)
            print(f"📁 {category_name}: ~{estimated_score}/{category_max}")
        print()

    # Display overall feedback if available
    if hasattr(score, "overall_feedback") and score.overall_feedback:
        print("💬 OVERALL FEEDBACK:")
        print("-" * 40)
        print(score.overall_feedback)
        print()

    # Display improvement guidance if available (JudgementModel specific)
    if hasattr(score, "improvement_prompt") and score.improvement_prompt:
        print("🔍 REMAINING ISSUES:")
        print("-" * 40)
        print(score.improvement_prompt)
        print()

    print("=" * 80)


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

    def get_target_score(self, target_percentage: float) -> int:
        """
        Calculate target score based on percentage.

        Args:
            target_percentage: Target percentage for world-class articles

        Returns:
            int: Target score in points
        """
        total_possible = self.get_total_possible_score()
        return int(total_possible * (target_percentage / 100))

    def analyze_score_gaps(
        self, score_results: ArticleScoreModel, target_percentage: float = 89.0
    ) -> Dict[str, Any]:
        """
        Analyze gaps between current and target scores.

        Args:
            score_results: Current scoring results
            target_percentage: Target percentage for analysis

        Returns:
            Dict with gap analysis including priority areas for improvement
        """
        category_weights = self.get_category_weights()
        target_total = self.get_target_score(target_percentage)
        current_total = score_results.total_score

        gap_analysis = {
            "total_gap": target_total - current_total,
            "current_percentage": score_results.percentage,
            "target_percentage": target_percentage,
            "category_gaps": {},
            "priority_categories": [],
        }

        # Analyze each category
        for category, results in score_results.category_scores.items():
            category_current = sum(r.score for r in results)
            category_max = category_weights.get(category, 0)
            category_target = int(category_max * (target_percentage / 100))
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
    print(f"Target Score (89%): {extractor.get_target_score(89.0)}")

    print("\nHigh Priority Criteria:")
    for category, question, points in extractor.get_high_priority_criteria():
        print(f"  {points} pts - {category}: {question[:60]}...")

    print("\n" + "=" * 50)
    print("CRITERIA FOR GENERATION:")
    print(extractor.get_criteria_for_generation())


# ==========================================================================
# SECTION 5: COMMAND LINE INTERFACE
# ==========================================================================


def read_file(filepath: str) -> str:
    """Read article text from a file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"❌ Error: File '{filepath}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error reading file '{filepath}': {e}")
        sys.exit(1)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Judge LinkedIn articles with emphasis on first-order thinking and Musk engineering principles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python li-article-judge.py "Your article text here"
  python li-article-judge.py --file article.txt
  python li-article-judge.py --analyze-file article.pdf
  python li-article-judge.py --analyze-file document.docx
  python li-article-judge.py --model "openrouter/anthropic/claude-3-haiku"

Scoring System (Total: 180 points):
  First-Order Thinking: 45 points (25%)
  Musk Engineering Principles: 75 points (42%) 
  Traditional criteria: 60 points (33%)

File Analysis (requires attachments library):
  --analyze-file supports: PDF, DOCX, images, and more
  Uses AI to extract article text from files automatically
  
Scoring Tiers:
  89%+: World-class — publish as is
  72%+: Strong, but tighten weak areas  
  56%+: Needs restructuring and sharper insights
  <56%: Rework before publishing
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "article_text",
        nargs="?",
        help="The article text to analyze (enclose in quotes)",
    )
    group.add_argument("--file", "-f", help="Path to file containing the article text")
    group.add_argument(
        "--analyze-file",
        "-a",
        help="Path to file to analyze using Attachments library (PDF, DOCX, images, etc.)",
    )

    parser.add_argument(
        "--model",
        "-m",
        default="openrouter/moonshotai/kimi-k2:free",
        help="LLM model to use for scoring (default: %(default)s)",
    )

    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress progress messages"
    )

    return parser.parse_args()


if __name__ == "__main__":
    print("used as part of a module")
