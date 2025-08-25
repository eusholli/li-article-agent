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
from typing import Dict, List, Optional

import dspy
from pydantic import BaseModel, Field, validator
from attachments.dspy import Attachments
from dspy_factory import DspyModelConfig
from context_window_manager import ContextWindowManager, ContextWindowError
import logging


# ==========================================================================
# SECTION 1: DATA STRUCTURES
# ==========================================================================


class ScoreResultModel(BaseModel):
    """
    🎯 PYDANTIC MODEL: Individual Scoring Result

    This is a Pydantic model that defines the structure of individual criterion scoring data.
    Pydantic ensures that the LLM returns data in exactly the format we expect.

    Think of this as a "template" that must be filled out completely for each criterion.
    Each field has a description that helps understand what data should be generated.
    """

    criterion: str = Field(
        ...,
        description="The specific criterion being evaluated (e.g., 'Q1: Does the article break down...')",
    )
    score: int = Field(
        ..., description="Weighted score for this criterion based on point value"
    )
    reasoning: str = Field(
        ..., description="Detailed explanation of why this score was given"
    )
    suggestions: str = Field(
        ..., description="Specific suggestions for improvement on this criterion"
    )


class ArticleScoreModel(BaseModel):
    """
    📊 PYDANTIC MODEL: Complete Article Scoring Results

    This is a Pydantic model that defines the structure of complete article analysis data.
    Pydantic ensures that all scoring components are present and properly formatted.

    Think of this as a comprehensive "report template" that must be filled out completely.
    Each field has a description that helps understand the expected analysis output.

    Why use Pydantic for article scoring?
    - Guarantees consistent output format across all analyses
    - Automatic validation of scoring data structure
    - Type safety for scoring calculations
    - Clear documentation of expected analysis components
    """

    total_score: int = Field(
        ..., description="Total weighted score achieved across all criteria"
    )
    max_score: int = Field(..., description="Maximum possible score (180 points total)")
    percentage: float = Field(
        ..., description="Percentage score (total_score/max_score * 100)"
    )
    category_scores: Dict[str, List[ScoreResultModel]] = Field(
        ...,
        description="Breakdown of scores by category with individual criterion results",
    )
    overall_feedback: str = Field(
        ...,
        description="Comprehensive feedback on article strengths and improvement areas",
    )
    performance_tier: str = Field(
        ...,
        description="Performance tier classification (World-class, Strong, Needs work, or Rework needed)",
    )
    word_count: Optional[int] = Field(
        None, description="Current word count of the article being scored"
    )


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

    # Article metadata
    word_count: int = Field(..., description="Word count of the evaluated article")

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
- overall_feedback: Comprehensive analysis (100+ characters)
- word_count: Article word count"""
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

    def forward(self, article_text: str) -> ArticleScoreModel:
        """Score an article across all criteria and generate comprehensive feedback."""

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

        # dspy.inspect_history(1)  # Inspect history for debugging

        # Calculate word count for the article
        word_count = len(article_text.split()) if article_text else 0

        return ArticleScoreModel(
            total_score=total_score,
            max_score=max_score,
            percentage=percentage,
            category_scores=category_scores,
            overall_feedback=feedback_result.output.overall_feedback,
            performance_tier=tier,
            word_count=word_count,
        )


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
            word_count=comprehensive_result.word_count,
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

    def forward(self, article_text: str) -> ArticleScoreModel:
        """
        Score an article using the fast single-call approach.

        Args:
            article_text: The article text to score

        Returns:
            ArticleScoreModel compatible with existing interfaces
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

            return legacy_result

        except Exception as e:
            print(f"⚠️ Fast scoring failed, falling back to original method: {str(e)}")
            logging.error(f"FastLinkedInArticleScorer failed: {str(e)}")

            # Fallback to original scorer if fast scoring fails
            original_scorer = LinkedInArticleScorer(self.models)
            return original_scorer(article_text)


# ==========================================================================
# SECTION 5: SCORING AND REPORTING FUNCTIONS
# ==========================================================================


def print_score_report(score: ArticleScoreModel) -> None:
    """
    Print a formatted report of the article scoring results.

    Args:
        score: The ArticleScoreModel object to format and print
    """
    print("\n" + "=" * 80)
    print("📋 LINKEDIN ARTICLE QUALITY SCORE REPORT")
    print("=" * 80)
    print(
        f"🎯 Overall Score: {score.total_score}/{score.max_score} ({score.percentage:.1f}%)"
    )
    print(f"🏆 Performance Tier: {score.performance_tier}")

    # Display word count if available
    if score.word_count is not None:
        print(f"📝 Word Count: {score.word_count} words")
    print()

    print("📊 CATEGORY BREAKDOWN:")
    print("-" * 40)
    for category, results in score.category_scores.items():
        category_score = sum(r.score for r in results)
        # Calculate category max based on actual point values
        category_max = sum(
            SCORING_CRITERIA[category][i].get("points", 5) for i in range(len(results))
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

    print("💬 OVERALL FEEDBACK:")
    print("-" * 40)
    print(score.overall_feedback)
    print()
    print("\n" + "=" * 80)
    print("📋 REPEAT ARTICLE QUALITY SCORE REPORT")
    print("=" * 80)
    print(
        f"🎯 Overall Score: {score.total_score}/{score.max_score} ({score.percentage:.1f}%)"
    )

    print("📊 CATEGORY SUMMARY:")
    print("-" * 40)
    for category, results in score.category_scores.items():
        category_score = sum(r.score for r in results)
        # Calculate category max based on actual point values
        category_max = sum(
            SCORING_CRITERIA[category][i].get("points", 5) for i in range(len(results))
        )
        print(f"📁 {category}: {category_score}/{category_max}")
    print()

    print(f"🏆 Performance Tier: {score.performance_tier}")
    print()


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
