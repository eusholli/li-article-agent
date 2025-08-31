#!/usr/bin/env python3
# li_judge_simple.py
"""
LinkedIn Article Judge — Simplified Binary Judging
--------------------------------------------------
This module preserves the SAME EXTERNAL INTERFACE as your judge:
- LinkedInArticleScorer(models).forward(article_text: str) -> dspy.Prediction[ArticleScoreModel]
- FastLinkedInArticleScorer(models).forward(article_text: str) -> dspy.Prediction[ArticleScoreModel]
- ComprehensiveLinkedInArticleJudge(models, passing_score_percentage=75, min_length=450, max_length=1200)
    .forward(article_versions: List[ArticleVersion]) -> dspy.Prediction[JudgementModel]

RADICAL SIMPLIFICATION (per your spec):
- No points. No severity.
- For EVERY criterion, the judge returns a strict POSITIVE/NEGATIVE decision (be hyper-critical).
- If NEGATIVE, it MUST include evidence (quotes/spans) and two levels of fixes:
    1) generic_fix  (general instruction for flipping to positive)
    2) recommendations (detailed, specific edits for THIS article)
- Scoring: Start at 100. Subtract 10 for EACH NEGATIVE criterion. Clamp to [0,100].
- improvement_prompt: includes ALL fixes/recommendations for the NEGATIVE criteria, combined.

This file is a drop-in alternative to the MQM version.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple, Optional

import dspy
from pydantic import BaseModel, Field
from dspy_factory import DspyModelConfig

# External models provided by your codebase
from models import ArticleVersion, JudgementModel
from word_count_manager import WordCountManager

# Simplified local SCORING_CRITERIA - binary judging without points/scales
SCORING_CRITERIA: Dict[str, List[Dict[str, Any]]] = {
    "First-Order Thinking": [
        {
            "question": "Does the article break down complex problems into fundamental components rather than relying on analogies or existing solutions?",
            "fix": "Replace analogies with a clear breakdown of the problem's fundamental components.",
        },
        {
            "question": "Does it challenge conventional wisdom by examining root assumptions and rebuilding from basic principles?",
            "fix": "Examine and challenge the root assumptions, then rebuild the argument from basic principles.",
        },
        {
            "question": "Does it avoid surface-level thinking and instead dig into the 'why' behind commonly accepted ideas?",
            "fix": "Dig deeper into the 'why' behind ideas rather than accepting them at face value.",
        },
    ],
    "Strategic Deconstruction & Synthesis": [
        {
            "question": "Does it deconstruct a complex system (a market, a company's strategy, a technology) into its fundamental components and incentives?",
            "fix": "Deconstruct the system into its fundamental components and explain the incentives driving each part.",
        },
        {
            "question": "Does it synthesize disparate information (e.g., history, financial data, product strategy, quotes) into a single, coherent thesis?",
            "fix": "Synthesize the disparate information into a single, coherent thesis.",
        },
        {
            "question": "Does it identify second- and third-order effects, explaining the cascading 'so what?' consequences of a core idea or event?",
            "fix": "Identify and explain the second- and third-order effects and their cascading consequences.",
        },
        {
            "question": "Does it introduce a durable framework or mental model (like 'The Bill Gates Line') that helps explain the system and is transferable to other contexts?",
            "fix": "Introduce a durable framework or mental model that explains the system and can be applied to other contexts.",
        },
        {
            "question": "Does it explain the fundamental 'why' behind events, rather than just describing the 'what'?",
            "fix": "Explain the fundamental 'why' behind events, not just the 'what'.",
        },
    ],
    "Hook & Engagement": [
        {
            "question": "Does the opening immediately grab attention with curiosity, emotion, or urgency?",
            "fix": "Start with a compelling hook that creates curiosity, emotion, or urgency.",
        },
        {
            "question": "Does the intro clearly state why this matters to the reader in the first 3 sentences?",
            "fix": "Clearly state why the topic matters to the reader within the first 3 sentences.",
        },
    ],
    "Storytelling & Structure": [
        {
            "question": "Is the article structured like a narrative (problem → tension → resolution → takeaway)?",
            "fix": "Structure the article as a narrative with problem, tension, resolution, and takeaway.",
        },
        {
            "question": "Are there specific, relatable examples or anecdotes?",
            "fix": "Include specific, relatable examples or anecdotes to illustrate points.",
        },
    ],
    "Authority & Credibility": [
        {
            "question": "Are claims backed by data, research, or credible sources?",
            "fix": "Back all claims with data, research, or credible sources.",
        },
        {
            "question": "Does the article demonstrate unique experience or perspective?",
            "fix": "Demonstrate unique experience or perspective to establish authority.",
        },
    ],
    "Idea Density & Clarity": [
        {
            "question": "Is there one clear, central idea driving the piece?",
            "fix": "Focus on one clear, central idea throughout the piece.",
        },
        {
            "question": "Is every sentence valuable (no filler or fluff)?",
            "fix": "Remove filler and fluff; ensure every sentence adds value.",
        },
    ],
    "Reader Value & Actionability": [
        {
            "question": "Does the reader walk away with practical, actionable insights?",
            "fix": "Provide practical, actionable insights that readers can apply.",
        },
        {
            "question": "Are lessons transferable beyond the example given?",
            "fix": "Ensure lessons are transferable to other contexts beyond the specific example.",
        },
    ],
    "Call to Connection": [
        {
            "question": "Does it end with a thought-provoking question or reflection prompt?",
            "fix": "End with a thought-provoking question or reflection prompt.",
        },
        {
            "question": "Does it use inclusive, community-building language ('we,' 'us,' shared goals)?",
            "fix": "Use inclusive, community-building language like 'we' and 'us' to foster connection.",
        },
    ],
}

# -----------------------------
# Utility
# -----------------------------


def normalize_ws(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def compute_performance_tier(percentage: float) -> str:
    if percentage >= 90:
        return "World-class"
    if percentage >= 75:
        return "Strong"
    if percentage >= 60:
        return "Needs work"
    return "Rework before publishing"


# -----------------------------
# Flatten criteria
# -----------------------------


def build_criteria_index() -> Tuple[List[Dict[str, Any]], Dict[str, Tuple[str, str]]]:
    """
    Returns:
      - flat list of criteria with ids: [{"id", "question", "category", "fix"}]
      - index: Q# -> (category, question)
    """
    flat: List[Dict[str, Any]] = []
    index: Dict[str, Tuple[str, str]] = {}
    q = 1
    for category, items in SCORING_CRITERIA.items():
        for c in items:
            cid = f"Q{q}"
            question = c.get("question", "").strip()
            fix = c.get("fix", "").strip()
            flat.append(
                {"id": cid, "question": question, "category": category, "fix": fix}
            )
            index[cid] = (category, question)
            q += 1
    return flat, index


# -----------------------------
# Pydantic output models (kept minimal)
# -----------------------------


class BinaryJudgeResult(BaseModel):
    """Pydantic model for the binary judge output."""

    passed: bool = Field(
        description="Whether the criterion passed (be hyper-critical; if unsure, false)"
    )
    rationale: str = Field(description="Concise explanation for the decision")
    evidence: List[str] = Field(
        default_factory=list,
        description="Quotes/spans that demonstrate failure (if passed, may be empty)",
    )
    generic_fix: str = Field(description="General instruction to flip to positive")
    recommendations: str = Field(
        description="Detailed, article-specific edit instructions"
    )


class ScoreResultModel(BaseModel):
    criterion: str
    score: int  # 100 if pass, 0 if fail (for display only)
    reasoning: str
    suggestions: str


class CategorySummary(BaseModel):
    category: str
    score: int  # sum of per-criterion 0/100 within category
    max_score: int  # 100 * (#criteria in category)
    percentage: float  # score/max_score * 100


class ArticleScoreModel(BaseModel):
    # Overall
    total_score: int  # 0..100 (100 - 10*negatives)
    max_score: int  # always 100
    percentage: float  # == total_score
    performance_tier: str
    word_count: Optional[int] = None

    # Per-category & per-criterion views
    category_scores: Dict[str, List[ScoreResultModel]]
    category_summaries: Dict[str, CategorySummary]

    overall_feedback: str


# -----------------------------
# DSPy Signatures
# -----------------------------


class BinaryJudgeSignature(dspy.Signature):
    """Judge a SINGLE criterion with a binary decision (positive/negative), evidence, and fixes."""

    article_text = dspy.InputField()
    criterion_id = dspy.InputField()
    criterion_question = dspy.InputField()

    output = dspy.OutputField(
        desc="""Strict JSON with:
    {
      "passed": boolean,            // be hyper-critical; if unsure, false
      "rationale": string,          // concise explanation for the decision
      "evidence": [string],         // quotes/spans that demonstrate failure (if passed, may be empty)
      "generic_fix": string,        // general instruction to flip to positive
      "recommendations": string     // detailed, article-specific edit instructions
    }"""
    )


class AllCriteriaBinaryJudgeSignature(dspy.Signature):
    """Judge ALL criteria at once (fast path).
    Be hyper-critical; if unsure, mark as failed.
    Be specific with evidence and fixes.
    Be super detailed with recommendations."""

    article_text = dspy.InputField()
    criteria_json = dspy.InputField(desc="JSON array: [{id, question}]")
    output = dspy.OutputField(
        desc="""Strict JSON with:
    {
      "items": [
        {
          "criterion_id": "Q1",
          "passed": boolean,
          "rationale": string,
          "evidence": [string],
          "generic_fix": string,
          "recommendations": string
        },
        ...
      ]
    }"""
    )


class OverallFeedbackSignature(dspy.Signature):
    """Short narrative coaching based on failed items."""

    failed_payload = dspy.InputField(
        desc="JSON of failed criteria with rationale/evidence/fixes"
    )
    output = dspy.OutputField(
        desc="4-6 sentence narrative: cross-cutting weaknesses and how to fix them."
    )


# -----------------------------
# Scorers
# -----------------------------


class LinkedInArticleScorer(dspy.Module):
    """Multiple LLM calls (one per criterion)."""

    def __init__(self, models: Dict[str, DspyModelConfig]):
        super().__init__()
        self.models = models
        self.judge_one = dspy.Predict(BinaryJudgeSignature)
        self.feedback = dspy.Predict(OverallFeedbackSignature)

    def forward(self, article_text: str) -> dspy.Prediction:
        flat, index = build_criteria_index()

        negatives = 0
        category_scores: Dict[str, List[ScoreResultModel]] = {}
        failed_items_for_feedback: List[Dict[str, Any]] = []

        for c in flat:
            with dspy.context(lm=self.models["judge"].dspy_lm):
                out = self.judge_one(
                    article_text=article_text,
                    criterion_id=c["id"],
                    criterion_question=c["question"],
                )
            passed = bool(out.get("passed", False))
            if not passed:
                negatives += 1
                failed_items_for_feedback.append(
                    {
                        "criterion_id": c["id"],
                        "criterion": c["question"],
                        "rationale": out.get("rationale", ""),
                        "evidence": out.get("evidence", []),
                        "generic_fix": out.get("generic_fix", ""),
                        "recommendations": out.get("recommendations", ""),
                    }
                )

            reasoning = normalize_ws(out.get("rationale", ""))
            if not passed and out.get("evidence"):
                ev = " | ".join(normalize_ws(e) for e in out["evidence"][:3])
                reasoning = (
                    f"{reasoning} Evidence: {ev}" if reasoning else f"Evidence: {ev}"
                )

            if not passed:
                evidence_list = out.get("evidence", [])
                evidence_text = ""
                if evidence_list:
                    evidence_text = f"Evidence: {' | '.join(normalize_ws(e) for e in evidence_list[:3])}\n"
                suggestions = f"Question {c['question']} failed.\n{evidence_text}In general, fix by {c['fix']}.\nSpecifically, fix by {normalize_ws(out.get('recommendations', ''))}"
            else:
                suggestions = "Maintain quality."

            category = index[c["id"]][0]
            category_scores.setdefault(category, []).append(
                ScoreResultModel(
                    criterion=f'{c["id"]}: {index[c["id"]][1]}',
                    score=100 if passed else 0,
                    reasoning=reasoning
                    or (
                        "Meets requirement." if passed else "Does not meet requirement."
                    ),
                    suggestions=suggestions
                    or ("Maintain quality." if passed else "Revise per fix guidance."),
                )
            )

        total = max(0, min(100, 100 - 10 * negatives))

        category_summaries: Dict[str, CategorySummary] = {}
        for cat, items in category_scores.items():
            cat_max = 100 * len(items)
            cat_score = sum(it.score for it in items)
            cat_pct = (cat_score / cat_max) * 100 if cat_max else 0.0
            category_summaries[cat] = CategorySummary(
                category=cat, score=cat_score, max_score=cat_max, percentage=cat_pct
            )

        with dspy.context(lm=self.models["judge"].dspy_lm):
            fb = self.feedback(failed_payload=json.dumps(failed_items_for_feedback))

        # Use WordCountManager for accurate word counting
        word_count_manager = WordCountManager(target_min=450, target_max=1200)
        model = ArticleScoreModel(
            total_score=total,
            max_score=100,
            percentage=float(total),
            performance_tier=compute_performance_tier(float(total)),
            word_count=word_count_manager.count_words(article_text),
            category_scores=category_scores,
            category_summaries=category_summaries,
            overall_feedback=normalize_ws(str(fb.output)),
        )

        return dspy.Prediction(output=model)


class FastLinkedInArticleScorer(dspy.Module):
    """Single LLM call to judge all criteria (fast path)."""

    def __init__(self, models: Dict[str, DspyModelConfig]):
        super().__init__()
        self.models = models
        self.judge_all = dspy.Predict(AllCriteriaBinaryJudgeSignature)
        self.feedback = dspy.Predict(OverallFeedbackSignature)

    def forward(self, article_text: str) -> dspy.Prediction:
        flat, index = build_criteria_index()
        payload = [{"id": c["id"], "question": c["question"]} for c in flat]

        # Create mapping from criterion_id to fix
        cid_to_fix = {c["id"]: c["fix"] for c in flat}

        with dspy.context(lm=self.models["judge"].dspy_lm):
            out = self.judge_all(
                article_text=article_text, criteria_json=json.dumps(payload)
            )

        # Parse the output - DSPy returns string that needs JSON parsing
        if hasattr(out, "output"):
            try:
                output_data = (
                    json.loads(out.output)
                    if isinstance(out.output, str)
                    else out.output
                )
                items = output_data.get("items", [])
            except (json.JSONDecodeError, AttributeError):
                items = []
        else:
            items = []

        negatives = 0
        category_scores: Dict[str, List[ScoreResultModel]] = {}
        failed_items_for_feedback: List[Dict[str, Any]] = []

        for it in items:
            cid = it.get("criterion_id")
            if cid not in index:
                continue
            category, question = index[cid]

            passed = bool(it.get("passed", False))
            if not passed:
                negatives += 1
                failed_items_for_feedback.append(
                    {
                        "criterion_id": cid,
                        "criterion": question,
                        "rationale": it.get("rationale", ""),
                        "evidence": it.get("evidence", []),
                        "generic_fix": it.get("generic_fix", ""),
                        "recommendations": it.get("recommendations", ""),
                    }
                )

            reasoning = normalize_ws(it.get("rationale", ""))
            ev_list = it.get("evidence", [])
            if not passed and ev_list:
                ev = " | ".join(normalize_ws(e) for e in ev_list[:3])
                reasoning = (
                    f"{reasoning} Evidence: {ev}" if reasoning else f"Evidence: {ev}"
                )

            if not passed:
                fix_text = cid_to_fix.get(cid, "")
                evidence_list = it.get("evidence", [])
                evidence_text = ""
                if evidence_list:
                    evidence_text = f"Evidence: {' | '.join(normalize_ws(e) for e in evidence_list[:3])}\n"
                suggestions = f"Question {question} failed.\n{evidence_text}In general, fix by {fix_text}.\nSpecifically, fix by {normalize_ws(it.get('recommendations', ''))}"
            else:
                suggestions = "Maintain quality."

            category_scores.setdefault(category, []).append(
                ScoreResultModel(
                    criterion=f"{cid}: {question}",
                    score=100 if passed else 0,
                    reasoning=reasoning
                    or (
                        "Meets requirement." if passed else "Does not meet requirement."
                    ),
                    suggestions=suggestions
                    or ("Maintain quality." if passed else "Revise per fix guidance."),
                )
            )

        total = max(0, min(100, 100 - 10 * negatives))

        category_summaries: Dict[str, CategorySummary] = {}
        for cat, items in category_scores.items():
            cat_max = 100 * len(items)
            cat_score = sum(it.score for it in items)
            cat_pct = (cat_score / cat_max) * 100 if cat_max else 0.0
            category_summaries[cat] = CategorySummary(
                category=cat, score=cat_score, max_score=cat_max, percentage=cat_pct
            )

        with dspy.context(lm=self.models["judge"].dspy_lm):
            fb = self.feedback(failed_payload=json.dumps(failed_items_for_feedback))

        # Use WordCountManager for accurate word counting
        word_count_manager = WordCountManager(target_min=450, target_max=1200)
        model = ArticleScoreModel(
            total_score=total,
            max_score=100,
            percentage=float(total),
            performance_tier=compute_performance_tier(float(total)),
            word_count=word_count_manager.count_words(article_text),
            category_scores=category_scores,
            category_summaries=category_summaries,
            overall_feedback=normalize_ws(str(fb.output)),
        )

        return dspy.Prediction(output=model)


# -----------------------------
# Comprehensive wrapper
# -----------------------------


class ComprehensiveLinkedInArticleJudge(dspy.Module):
    """
    Returns a JudgementModel and keeps the external API the same.
    - Uses FastLinkedInArticleScorer by default.
    - Exit condition is simply percentage >= passing_score_percentage AND length in range.
    - improvement_prompt concatenates ALL fixes/recommendations for failed criteria.
    """

    def __init__(
        self,
        models: Dict[str, DspyModelConfig],
        passing_score_percentage: float = 75.0,
        min_length: int = 450,
        max_length: int = 1200,
        fast: bool = True,
    ):
        super().__init__()
        self.models = models
        self.passing_score_percentage = float(passing_score_percentage)
        self.min_length = int(min_length)
        self.max_length = int(max_length)
        self.scorer = (
            FastLinkedInArticleScorer(models) if fast else LinkedInArticleScorer(models)
        )

    def forward(self, article_versions: List[ArticleVersion]) -> dspy.Prediction:
        if not article_versions:
            raise ValueError("No article versions provided.")
        latest = article_versions[-1]
        article_text = latest.content

        # Score
        pred = self.scorer(article_text)
        score: ArticleScoreModel = pred.output  # type: ignore

        # Build improvement prompt from failed items inside category_scores
        fixes: List[str] = []
        for cat, items in score.category_scores.items():
            for it in items:
                if it.score == 0:
                    if it.suggestions:
                        fixes.append(it.suggestions)

        # Length gate + final meets
        wc = score.word_count or 0
        length_ok = self.min_length <= wc <= self.max_length
        meets = bool(length_ok and (score.percentage >= self.passing_score_percentage))

        # Always populate improvement_prompt with advice when document needs improvement
        if not fixes and meets:
            improvement_prompt = "All criteria are satisfactory. No changes required."
        elif fixes:
            improvement_prompt = (
                "Address the following before approval:\n\n" + "\n\n".join(fixes)
            )
            if not length_ok:
                improvement_prompt += f"\n\nLength out of range: {wc} words (target {self.min_length}-{self.max_length})."
        else:
            # No failed criteria but length is wrong - still provide improvement advice
            improvement_prompt = "Address the following before approval:\n\n"
            if not length_ok:
                improvement_prompt += f"Length out of range: {wc} words (target {self.min_length}-{self.max_length}).\n\n"
            improvement_prompt += "Consider reviewing the article for potential improvements in content depth, clarity, or engagement to ensure it meets all quality standards."

        judgement = JudgementModel(
            total_score=score.total_score,
            max_score=score.max_score,
            percentage=score.percentage,
            performance_tier=score.performance_tier,
            word_count=wc,
            meets_requirements=meets,
            improvement_prompt=improvement_prompt,
            focus_areas=(
                ", ".join(
                    sorted(
                        score.category_summaries.keys(),
                        key=lambda c: score.category_summaries[c].percentage,
                    )[:3]
                )
                if score.category_summaries
                else "None"
            ),
            overall_feedback=score.overall_feedback,
        )

        return dspy.Prediction(output=judgement)


# ==========================================================================
# SCORING AND REPORTING FUNCTIONS
# ==========================================================================


def get_criteria_for_generation() -> str:
    """
    Get criteria formatted specifically for article generation prompts using local SCORING_CRITERIA.

    Returns:
        str: Criteria formatted for LLM generation prompts
    """
    generation_prompt = []
    generation_prompt.append("SCORING CRITERIA FOR ARTICLE GENERATION:")
    generation_prompt.append(
        "Your article will be evaluated on these binary criteria (pass/fail):\n"
    )

    # Calculate category weights (number of criteria per category)
    category_weights = {}
    for category, criteria_list in SCORING_CRITERIA.items():
        category_weights[category] = len(criteria_list)

    # Sort categories by weight (highest first)
    sorted_categories = sorted(
        category_weights.items(), key=lambda x: x[1], reverse=True
    )

    for category, total_criteria in sorted_categories:
        generation_prompt.append(f"**{category}** ({total_criteria} criteria):")

        criteria_list = SCORING_CRITERIA[category]
        for i, criterion in enumerate(criteria_list, 1):
            question = criterion["question"]
            fix = criterion.get("fix", "")

            generation_prompt.append(f"  {i}. {question}")

            # Add fix guidance for better generation
            if fix:
                generation_prompt.append(f"     Fix if failed: {fix}")

        generation_prompt.append("")

    # Dynamic optimization priorities based on category weights
    generation_prompt.append("OPTIMIZATION PRIORITIES:")
    priority_num = 1
    for category, weight in sorted_categories[:4]:  # Top 4 categories by weight
        generation_prompt.append(
            f"{priority_num}. Focus on {category} ({weight} criteria)"
        )
        priority_num += 1

    # Add word count guidance if available
    generation_prompt.append(
        f"{priority_num}. Target appropriate length for content depth"
    )
    generation_prompt.append("")

    generation_prompt.append("JUDGING INSTRUCTIONS:")
    generation_prompt.append("- Be hyper-critical: if unsure, mark as failed")
    generation_prompt.append(
        "- Include evidence and specific recommendations when criteria fail"
    )

    return "\n".join(generation_prompt)


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

    # For simplified JudgementModel, show basic category breakdown
    print("📊 CATEGORY SUMMARY:")
    print("-" * 40)
    total_criteria = sum(len(criteria) for criteria in SCORING_CRITERIA.values())
    total_possible = (
        total_criteria * 100
    )  # Each criterion is worth 100 points in binary system
    for category_name, criteria in SCORING_CRITERIA.items():
        category_criteria_count = len(criteria)
        category_max = category_criteria_count * 100
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
