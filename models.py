#!/usr/bin/env python3
"""
Shared Data Models for LinkedIn Article Generator

This module contains shared Pydantic models used across multiple components
to avoid circular import dependencies while maintaining clean architecture.
"""

import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from pydantic import BaseModel, Field


@dataclass
class ArticleVersion:
    """Represents a version of an article with its metadata."""

    writer_id: int
    version_id: int
    content: str
    context: str
    recreate_ctx: bool
    judgement: "JudgementModel"
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class JudgementModel(BaseModel):
    """
    🎯 PYDANTIC MODEL: Complete Article Judgement with Improvement Guidance

    This model encapsulates all judging logic including scoring, requirements checking,
    and ready-to-use improvement prompts. It provides a clean interface between
    the judge and generator components.

    Benefits:
    - Clean separation of concerns (judge handles all analysis)
    - Encapsulated improvement logic
    - Ready-to-use prompts for generator
    - Configuration-driven decision making
    """

    # Core scoring results
    total_score: int = Field(..., description="Total score achieved (0-100)")
    max_score: int = Field(..., description="Maximum possible score (100 points)")
    percentage: float = Field(..., ge=0, le=100, description="Percentage score")
    performance_tier: str = Field(..., description="Performance tier classification")
    word_count: int = Field(..., description="Current word count of the article")

    # Decision logic based on configuration
    meets_requirements: bool = Field(
        ..., description="Whether article meets both score and length requirements"
    )

    # Ready-to-use improvement guidance
    improvement_prompt: str = Field(
        ...,
        min_length=50,
        description="Complete improvement prompt ready for ArticleImprovementSignature",
    )

    overall_feedback: Optional[str] = Field(
        None, description="Comprehensive feedback (optional for detailed analysis)"
    )

    # Fact-checking results (optional, only populated when fact-checking runs)
    fact_check_result: Optional["FactCheckResult"] = Field(
        None, description="Fact-checking results if fact-checking was performed"
    )


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


# ==========================================================================
# FACT-CHECKING MODELS
# ==========================================================================


class FactCheckResult(BaseModel):
    """
    📋 PYDANTIC MODEL: Complete Fact-Checking Results

    Comprehensive results of fact-checking an article, including all validations,
    suggestions, and overall assessment. This model is used to track fact-checking
    status and integrate with the existing judging system.
    """

    total_claims_found: int = Field(
        ..., description="Total number of factual claims identified"
    )
    claims_with_citations: int = Field(
        ..., description="Number of claims that already have citations"
    )
    valid_citations: int = Field(..., description="Number of citations that are valid")
    invalid_citations: int = Field(
        ..., description="Number of citations that are invalid"
    )
    uncited_claims: int = Field(
        ..., description="Number of factual claims without citations"
    )

    fact_check_passed: bool = Field(
        ..., description="Whether the article passes fact-checking requirements"
    )
    improvement_needed: bool = Field(
        ..., description="Whether improvements are needed for fact-checking compliance"
    )

    summary_feedback: str = Field(
        ..., description="Summary of fact-checking results and recommendations"
    )
    detailed_feedback: str = Field(
        ..., description="Detailed feedback with specific actions needed"
    )
