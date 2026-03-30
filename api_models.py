"""
Pydantic request/response models for the LinkedIn Article Generator API.
"""

from pydantic import BaseModel, Field
from typing import Optional


class GenerateRequest(BaseModel):
    """Request body for POST /articles/generate."""

    draft: str = Field(..., min_length=50, description="Article draft or outline text")
    target_score: float = Field(
        89.0, ge=0.0, le=100.0, description="Target quality score percentage"
    )
    max_iterations: int = Field(
        10, ge=1, le=50, description="Maximum improvement iterations"
    )
    word_count_min: int = Field(2000, ge=100, description="Minimum target word count")
    word_count_max: int = Field(2500, ge=100, description="Maximum target word count")
    model: str = Field(
        "gemini/gemini-2.5-flash",
        description="Default fallback model if component-specific models are not set",
    )
    generator_model: Optional[str] = Field(
        "gemini/gemini-2.5-pro",
        description="Model for article generation — premium model for quality writing (overrides model)",
    )
    judge_model: Optional[str] = Field(
        "gemini/gemini-2.5-flash",
        description="Model for article scoring — efficient model for structured analytical evaluation (overrides model)",
    )
    rag_model: Optional[str] = Field(
        "gemini/gemini-2.5-flash",
        description="Model for search query generation — efficient model for utility task (overrides model)",
    )
    humanizer_model: Optional[str] = Field(
        None,
        description="Model for humanization — defaults to generator_model if not set",
    )
    recreate_ctx: bool = Field(
        False,
        description="Regenerate RAG context on each improvement iteration (default: reuse initial context)",
    )

    model_config = {"json_schema_extra": {
        "example": {
            "draft": "AI is transforming how businesses operate. Most leaders focus on efficiency gains. But the real disruption is happening at the decision layer — where human judgment meets machine intelligence.",
            "target_score": 89.0,
            "max_iterations": 10,
            "word_count_min": 2000,
            "word_count_max": 2500,
        }
    }}
