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
from dspy_factory import setup_dspy_provider
from attachments.dspy import Attachments


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
# SECTION 3: VALIDATION FUNCTIONS
# ==========================================================================


def validate_criterion_output(output) -> bool:
    """
    Validate that criterion scoring output has all required fields and proper format.

    This function is used with DSPy's suggest method to ensure the LLM returns
    properly formatted responses with all required fields.

    Args:
        output: The output from ArticleCriterionScorer

    Returns:
        bool: True if output is valid, False otherwise
    """
    required_fields = ["reasoning", "score", "suggestions"]

    # Check if output has all required fields
    if not all(hasattr(output, field) for field in required_fields):
        return False

    # Check if score is valid integer between 1-5
    try:
        score = int(output.score)
        if not (1 <= score <= 5):
            return False
    except (ValueError, TypeError):
        return False

    # Check if reasoning and suggestions are non-empty strings
    if not (
        output.reasoning
        and output.suggestions
        and len(str(output.reasoning).strip()) > 10
        and len(str(output.suggestions).strip()) > 10
    ):
        return False

    return True


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

    score: int = dspy.OutputField(desc="Score from 1-5 for this criterion")
    reasoning = dspy.OutputField(
        desc="Detailed explanation of why this score was given"
    )
    suggestions = dspy.OutputField(desc="Specific suggestions for improvement")


class OverallFeedbackGenerator(dspy.Signature):
    """Generate overall feedback and performance tier for a LinkedIn article."""

    article_text = dspy.InputField(desc="The full text of the LinkedIn article")
    total_score = dspy.InputField(desc="Total score achieved out of maximum possible")
    category_breakdown = dspy.InputField(desc="Breakdown of scores by category")

    overall_feedback = dspy.OutputField(
        desc="Comprehensive feedback on the article's strengths and areas for improvement"
    )
    performance_tier = dspy.OutputField(
        desc="Performance tier: World-class, Strong, Needs work, or Rework needed"
    )


class FileArticleExtractor(dspy.Signature):
    """Extract clean article text from a file attachment for LinkedIn article analysis."""

    file_content: Attachments = dspy.InputField(
        desc="The file containing the LinkedIn article (PDF, DOCX, etc.)"
    )
    article_text: str = dspy.OutputField(
        desc="Clean, readable article text extracted from the file, ready for analysis"
    )


class LinkedInArticleScorer(dspy.Module):
    """Complete LinkedIn article scoring system using DSPy."""

    def __init__(self):
        super().__init__()
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

                # Get score for this criterion with retry logic
                result = None
                max_retries = 3

                for attempt in range(max_retries):
                    try:
                        result = self.criterion_scorer(
                            article_text=article_text,
                            criterion_question=criterion["question"],
                            scale_description=scale_desc,
                        )

                        # dspy.inspect_history(1)  # Inspect history for debugging

                        # Validate the result using our validation function
                        if validate_criterion_output(result):
                            break  # Success, exit retry loop
                        else:
                            print(
                                f"⚠️ Attempt {attempt + 1}: Invalid output format, retrying..."
                            )
                            if attempt == max_retries - 1:
                                # Last attempt failed, create fallback
                                result = None
                    except Exception as e:
                        print(
                            f"⚠️ Attempt {attempt + 1}: Scoring failed ({str(e)}), retrying..."
                        )
                        if attempt == max_retries - 1:
                            # Last attempt failed, create fallback
                            result = None

                # Handle fallback if all retries failed
                if result is None or not validate_criterion_output(result):
                    print(
                        f"⚠️ All retries failed for {criterion_id}, using fallback response"
                    )

                    # Create a fallback result object
                    class FallbackResult:
                        def __init__(self):
                            self.score = 3  # Default middle score
                            self.reasoning = f"Unable to analyze this criterion due to response format issues. Criterion: {criterion['question'][:100]}..."
                            self.suggestions = "Please review this criterion manually for more specific feedback."

                    result = FallbackResult()

                # Parse and validate score
                try:
                    raw_score = int(result.score)
                    raw_score = max(1, min(5, raw_score))  # Clamp to 1-5 range
                except (ValueError, AttributeError):
                    raw_score = 3  # Default to middle score if parsing fails

                # Calculate weighted score based on criterion points
                weighted_score = (raw_score * criterion_points) // 5
                total_score += weighted_score

                score_result = ScoreResultModel(
                    criterion=f"{criterion_id}: {criterion['question']}",
                    score=weighted_score,
                    reasoning=str(result.reasoning),
                    suggestions=str(result.suggestions),
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

        feedback_result = self.feedback_generator(
            article_text=article_text,
            total_score=f"{total_score}/{max_score}",
            category_breakdown=category_breakdown,
        )

        # dspy.inspect_history(1)  # Inspect history for debugging

        return ArticleScoreModel(
            total_score=total_score,
            max_score=max_score,
            percentage=percentage,
            category_scores=category_scores,
            overall_feedback=feedback_result.overall_feedback,
            performance_tier=tier,
        )


# ==========================================================================
# SECTION 4: SCORING AND REPORTING FUNCTIONS
# ==========================================================================


def initialize_scorer(
    model_name: str = "openrouter/moonshotai/kimi-k2:free",
) -> LinkedInArticleScorer:
    """
    Initialize the LinkedIn article scoring system.

    Args:
        model_name: The LLM model to use for scoring

    Returns:
        LinkedInArticleScorer: Configured scoring system
    """
    setup_dspy_provider(model_name)
    return LinkedInArticleScorer()


def score_article(
    article_text: str, scorer: Optional[LinkedInArticleScorer] = None
) -> ArticleScoreModel:
    """
    Score a LinkedIn article using the comprehensive 18-point checklist.

    Args:
        article_text: The full text of the article to score
        scorer: Optional pre-initialized scorer (will create new one if None)

    Returns:
        ArticleScoreModel: Complete scoring results with feedback
    """
    if scorer is None:
        print("🚀 Initializing LinkedIn Article Scorer...")
        scorer = initialize_scorer()

    return scorer(article_text)


def analyze_file(
    file_path: str,
    model_name: str = "openrouter/moonshotai/kimi-k2:free",
    scorer: Optional[LinkedInArticleScorer] = None,
) -> ArticleScoreModel:
    """
    Analyze a LinkedIn article from a file using the Attachments library.

    This function uses the Attachments library to extract text from various file formats
    (PDF, DOCX, images, etc.) and then scores the extracted article text using the
    comprehensive 18-point LinkedIn article quality checklist.

    Args:
        file_path: Path to the file containing the article (supports PDF, DOCX, images, etc.)
        model_name: The LLM model to use for scoring and text extraction
        scorer: Optional pre-initialized scorer (will create new one if None)

    Returns:
        ArticleScoreModel: Complete scoring results with feedback

    Raises:
        ImportError: If the attachments library is not installed
        FileNotFoundError: If the specified file doesn't exist
        Exception: For other file processing or analysis errors
    """

    print(f"📄 Loading file: {file_path}")

    try:
        # Initialize DSPy provider
        setup_dspy_provider(model_name)

        # Load file using Attachments library
        file_attachment = Attachments(file_path)

        # Check if we got any content
        if not file_attachment.text or len(file_attachment.text.strip()) < 50:
            # Try to extract text using DSPy if direct text extraction is insufficient
            print("🔄 Extracting article text from file...")
            extractor = dspy.ChainOfThought(FileArticleExtractor)
            extraction_result = extractor(file_content=file_attachment)
            article_text = extraction_result.article_text
        else:
            # Use the directly extracted text
            article_text = file_attachment.text

        # Validate extracted text
        if not article_text or len(article_text.strip()) < 50:
            raise ValueError(
                f"Could not extract sufficient text from file '{file_path}'. "
                f"Extracted {len(article_text) if article_text else 0} characters. "
                "Please ensure the file contains readable article content."
            )

        print(f"✅ Successfully extracted {len(article_text)} characters from file")
        print(f"🤖 Using model: {model_name}")

        # Score the extracted article text using existing scoring system
        return score_article(article_text, scorer)

    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")
    except Exception as e:
        raise Exception(f"Error analyzing file '{file_path}': {str(e)}")


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


def main():
    """Main entry point for the LinkedIn article judge."""
    args = parse_arguments()

    try:
        # Handle different input methods
        if args.analyze_file:
            # Use Attachments library for file analysis
            if not args.quiet:
                print(
                    f"🔍 Analyzing file using Attachments library: {args.analyze_file}"
                )
            results = analyze_file(args.analyze_file, args.model)

        elif args.file:
            # Traditional text file reading
            article_text = read_file(args.file)
            if not args.quiet:
                print(f"📄 Loaded article from: {args.file}")
                print(f"📝 Article length: {len(article_text)} characters")
                print(f"🤖 Using model: {args.model}")

            # Validate article text
            if not article_text or len(article_text.strip()) < 50:
                print("❌ Error: Article text is too short (minimum 50 characters)")
                sys.exit(1)

            # Score the article text
            scorer = initialize_scorer(args.model)
            results = score_article(article_text, scorer)

        else:
            # Direct text input
            article_text = args.article_text

            # Validate article text
            if not article_text or len(article_text.strip()) < 50:
                print("❌ Error: Article text is too short (minimum 50 characters)")
                sys.exit(1)

            if not args.quiet:
                print(f"📝 Article length: {len(article_text)} characters")
                print(f"🤖 Using model: {args.model}")

            # Score the article text
            scorer = initialize_scorer(args.model)
            results = score_article(article_text, scorer)

        # Print results
        print_score_report(results)

        # Exit with appropriate code based on score
        if results.percentage >= 72:
            sys.exit(0)  # Success for strong articles
        elif results.percentage >= 56:
            sys.exit(1)  # Warning for articles needing work
        else:
            sys.exit(2)  # Error for articles needing major rework

    except KeyboardInterrupt:
        print("\n❌ Analysis interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
