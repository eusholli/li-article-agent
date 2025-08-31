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

    version: int
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
    focus_areas: str = Field(
        ...,
        description="Brief summary of focus areas for logging and progress tracking",
    )

    overall_feedback: Optional[str] = Field(
        None, description="Comprehensive feedback (optional for detailed analysis)"
    )
