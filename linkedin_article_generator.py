#!/usr/bin/env python3
"""
LinkedIn Article Generator

Main orchestrator class that implements the iterative article generation and improvement
process using DSPy, scoring criteria, and word count management.
"""

import dspy
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import json
import time
import re
import asyncio

from li_article_judge import (
    LinkedInArticleScorer,
    FastLinkedInArticleScorer,
    ArticleScoreModel,
)
from criteria_extractor import CriteriaExtractor
from word_count_manager import WordCountManager
from dspy_factory import DspyModelConfig
from context_window_manager import ContextWindowManager, ContextWindowError
from rag_fast import retrieve_and_pack


@dataclass
class ArticleVersion:
    """Represents a version of an article with its metadata."""

    version: int
    content: str
    word_count: int
    score_results: Optional[ArticleScoreModel] = (
        None  # Will come from prediction.output
    )
    improvement_feedback: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class ArticleGenerationSignature(dspy.Signature):
    """Generate a complete LinkedIn article from draft/outline with RAG context and markdown formatting."""

    original_draft = dspy.InputField(
        desc="Original draft to expand on key points if necessary",
    )
    context = dspy.InputField(
        desc="String containing relevant content with inline markdown citations already formatted. Citations appear as [specific claim or data point](source_url) within the text.",
        default="",
    )
    scoring_criteria = dspy.InputField(desc="Complete scoring criteria for reference")
    word_count_guidance = dspy.InputField(desc="Word count optimization guidance")

    generated_article = dspy.OutputField(
        desc="""Generate a complete LinkedIn article in markdown format with these requirements:

        MARKDOWN FORMATTING:
        - Use clear header hierarchy (# ## ###)
        - Include bullet points and numbered lists where appropriate
        - Use **bold** and *italic* emphasis for key points
        - Professional paragraph structure with engaging subheadings

        CITATION CREATION:
        - The context string already contains properly formatted inline citations as [specific claim or data point](source_url)
        - Use these pre-formatted citations directly when incorporating relevant information from the context
        - Example: If context contains "Company revenue was [$50 billion](https://example.com)", use this exact citation format
        - ONLY cite information that directly appears in the provided context string with its existing citations
        - Present analysis, opinions, and synthesis as uncited content
        - Aim for 3-8 citations per article by utilizing the pre-formatted citations from the context

        CONTENT REQUIREMENTS:
        - Expand the draft/outline into a comprehensive LinkedIn article
        - Maintain professional LinkedIn tone and structure
        - Objective and third-person, with a more structured, business/technical tone
        - Address all key points from the original draft

        WORD LENGTH ADJUSTMENT:
        - Follow the specific word count guidance provided
        - If expansion is needed, focus on areas that improve both length and quality
        - If condensation is needed, preserve all key insights and arguments
        - Use the guidance to strategically adjust content length while maintaining article quality"""
    )


class ArticleImprovementSignature(dspy.Signature):
    """Improve an existing article based on scoring feedback and criteria while maintaining consistency with original draft."""

    current_article = dspy.InputField(desc="Current version of the article")
    original_draft = dspy.InputField(
        desc="Original draft for reference to maintain key points"
    )
    context = dspy.InputField(
        desc="String containing relevant content with inline markdown citations already formatted. Citations appear as [specific claim or data point](source_url) within the text.",
        default="",
    )
    score_feedback = dspy.InputField(
        desc="Detailed scoring feedback and improvement suggestions"
    )
    scoring_criteria = dspy.InputField(desc="Complete scoring criteria for reference")
    word_count_guidance = dspy.InputField(desc="Word count optimization guidance")
    improvement_focus = dspy.InputField(desc="Specific areas to focus improvement on")

    improved_article = dspy.OutputField(
        desc="""Generate an improved LinkedIn article in markdown format with these requirements:

        MARKDOWN FORMATTING:
        - Use clear header hierarchy (# ## ###)
        - Include bullet points and numbered lists where appropriate
        - Use **bold** and *italic* emphasis for key points
        - Professional paragraph structure with engaging subheadings

        CITATION CREATION:
        - The context string already contains properly formatted inline citations as [specific claim or data point](source_url)
        - Use these pre-formatted citations directly when incorporating relevant information from the context
        - Example: If context contains "Company revenue was [$50 billion](https://example.com)", use this exact citation format
        - ONLY cite information that directly appears in the provided context string with its existing citations
        - Present analysis, opinions, and synthesis as uncited content
        - Aim for 3-8 citations per article by utilizing the pre-formatted citations from the context

        CONTENT REQUIREMENTS:
        - Address the scoring feedback while maintaining original draft key points
        - Maintain professional LinkedIn tone and structure

        IMPROVEMENT STRATEGY:
        - Focus on the specific improvement areas identified in the feedback
        - Address scoring weaknesses with targeted improvements
        - Maintain consistency with the original draft's key points

        WORD LENGTH ADJUSTMENT:
        - Follow the specific word count guidance provided
        - If expansion is needed, focus on weak scoring areas to improve both length and quality
        - If condensation is needed, preserve all key insights and arguments
        - Use the guidance to strategically adjust content length while maintaining article quality"""
    )


class LinkedInArticleGenerator:
    """
    Main class for generating world-class LinkedIn articles using iterative improvement.

    This class orchestrates the simplified process:
    1. Use the initial draft as Version 1
    2. Score the article using li_article_judge
    3. Analyze weaknesses and generate improvement guidance
    4. Iteratively improve until target score (≥89%) is achieved
    """

    def __init__(
        self,
        target_score_percentage: float,
        max_iterations: int,
        word_count_min: int,
        word_count_max: int,
        models: Dict[str, DspyModelConfig],
    ):
        """
        Initialize the LinkedIn Article Generator.

        Args:
            target_score_percentage: Target score percentage for world-class articles
            max_iterations: Maximum number of improvement iterations
            word_count_min: Minimum target word count
            word_count_max: Maximum target word count
            generator_model: Optional model name for article generation components
            judge_model: Optional model name for article scoring components
            rag_model: Optional model name for RAG retrieval components
        """
        self.target_score_percentage = target_score_percentage
        self.max_iterations = max_iterations

        # Store model preferences
        self.models = models

        # Initialize context window manager
        self.context_manager = ContextWindowManager(models["generator"])

        # self.judge = LinkedInArticleScorer(models=models)
        self.judge = FastLinkedInArticleScorer(models=models)
        self.criteria_extractor = CriteriaExtractor()
        self.word_count_manager = WordCountManager(word_count_min, word_count_max)

        # Initialize DSPy modules with optional model-specific LM instances

        self.generator = dspy.ChainOfThought(ArticleGenerationSignature)
        self.improver = dspy.ChainOfThought(ArticleImprovementSignature)

        # Track generation history
        self.versions: List[ArticleVersion] = []
        self.generation_log: List[str] = []
        self.original_draft: Optional[str] = None

    def _perform_rag_search(self, draft_text: str, verbose: bool = True) -> str:
        """
        Perform comprehensive RAG search and return context with inline citations.

        Args:
            draft_text: The draft article text to extract search queries from
            verbose: Whether to print progress updates

        Returns:
            Context with inline citations
        """
        try:

            ctx, urls = asyncio.run(retrieve_and_pack(draft_text, models=self.models))

            if verbose:
                print(
                    f"✅ Retrieved context len: {len(ctx)}: URLs: {urls if urls else 'None'}"
                )

            if ctx:
                return ctx
            else:
                if verbose:
                    print("⚠️ No valid content retrieved from RAG search")
                return ""

        except Exception as e:
            if verbose:
                print(f"⚠️ RAG search failed: {e}")
            return ""

    def generate_article(
        self, initial_draft: str, verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a world-class LinkedIn article from a draft or outline.

        Args:
            initial_draft: Initial draft article or outline
            verbose: Whether to print progress updates

        Returns:
            Dict containing final article, score, and generation metadata
        """
        return self.generate_article_with_context(initial_draft, {}, verbose)

    def generate_article_with_context(
        self, initial_draft: str, context: Dict[str, str] = {}, verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a world-class LinkedIn article from a draft or outline with web context.

        Args:
            initial_draft: Initial draft article or outline
            context: Dictionary mapping URLs to their text content for citation selection
            verbose: Whether to print progress updates

        Returns:
            Dict containing final article, score, and generation metadata
        """
        if verbose:
            print("🚀 Starting LinkedIn Article Generation Process")
            print("=" * 60)

        # Clear previous generation data
        self.versions.clear()
        self.generation_log.clear()
        self.original_draft = initial_draft
        self.search_context = context or {}

        if context and verbose:
            print(f"🌐 Using web context: {len(context)} URLs")

        # Generate initial markdown article from draft/outline (Version 1)
        if verbose:
            print(f"📝 Generating initial markdown article from draft...")

        initial_article = self._generate_initial_article(
            initial_draft, context, verbose
        )

        word_count = self.word_count_manager.count_words(initial_article)

        initial_version = ArticleVersion(
            version=1, content=initial_article, word_count=word_count
        )
        self.versions.append(initial_version)

        if verbose:
            print(f"📝 Generated initial article: {word_count} words")

        self.generation_log.append(
            f"Version 1: Generated initial markdown article from draft ({word_count} words)"
        )

        # Start iterative improvement process with the generated article
        final_result = self._iterative_improvement_process(initial_article, verbose)

        if verbose:
            self._print_final_summary(final_result)

        return final_result

    def _iterative_improvement_process(
        self, initial_article: str, verbose: bool
    ) -> Dict[str, Any]:
        """Run the iterative improvement process with combined quality and length validation."""
        current_article = initial_article
        iteration = 0
        # generate default score_results to avoid reference before assignment
        score_results = ArticleScoreModel(
            total_score=0,
            percentage=0.0,
            word_count=0,
            overall_feedback="",
            performance_tier="",
            category_scores={},
            max_score=0,
        )

        while iteration < self.max_iterations:
            iteration += 1

            if verbose:
                print(f"\n🔄 Iteration {iteration}: Scoring and Analysis")
                print("-" * 40)

            # Score current article (returns DSPy Prediction)
            prediction = self.judge(current_article)
            score_results = prediction.output
            score_results.word_count = self.word_count_manager.count_words(
                current_article
            )

            # if verbose then print score result details and the recommended improvements
            # and the current word count and length status
            if verbose:
                print(
                    f"📊 Current Score: {score_results.total_score}/{self.criteria_extractor.get_total_possible_score()} ({score_results.percentage:.1f}%)"
                )

                print(f"📝 Current Word Count: {score_results.word_count} words")
                print(f"🎯 Target Score: ≥{self.target_score_percentage}%")
                print(
                    f"📏 Target Word Count: {self.word_count_manager.target_min}-{self.word_count_manager.target_max}"
                )
                print("🔍 Improvement Suggestions:")
                for category, results in score_results.category_scores.items():
                    for r in results:
                        if hasattr(r, "suggestions") and r.suggestions:
                            print(f"  [{category}] {r.suggestions}")

            # Update current version with score
            if self.versions:
                self.versions[-1].score_results = score_results

            current_percentage = score_results.percentage
            length_status = self.word_count_manager.get_word_count_status(
                score_results.word_count
            )

            # Check if both targets achieved (combined quality + length validation)
            quality_achieved = current_percentage >= self.target_score_percentage
            length_achieved = length_status["within_range"]

            if quality_achieved and length_achieved:
                if verbose:
                    print(
                        f"🎉 BOTH TARGETS ACHIEVED! Article reached world-class status with optimal length!"
                    )

                self.generation_log.append(
                    f"Iteration {iteration}: Both targets achieved (Score: {current_percentage:.1f}%, Words: {score_results.word_count})"
                )
                break

            elif quality_achieved and not length_achieved:
                if verbose:
                    print(
                        f"✅ Quality target achieved, but length needs adjustment: {length_status['guidance']}"
                    )

            elif not quality_achieved and length_achieved:
                if verbose:
                    print(
                        f"✅ Length target achieved, but quality needs improvement: {current_percentage:.1f}% vs {self.target_score_percentage}% target"
                    )

            else:
                if verbose:
                    print(
                        f"⚠️  Both targets need work: Quality ({current_percentage:.1f}%) and Length ({length_status['guidance']})"
                    )

            # Analyze improvement needs
            improvement_analysis = self._analyze_improvement_needs(
                score_results, current_article
            )

            if verbose:
                print(f"🔍 Focus Areas: {improvement_analysis['focus_summary']}")

            # Generate improved version
            if verbose:
                print(f"✏️  Generating improved version...")

            improved_article = self._generate_improved_version(
                current_article, score_results, improvement_analysis, verbose
            )

            # Validate improvement
            new_word_count = self.word_count_manager.count_words(improved_article)

            # Create new version
            version = ArticleVersion(
                version=iteration + 1,
                content=improved_article,
                word_count=new_word_count,
                improvement_feedback=improvement_analysis["detailed_feedback"],
            )
            self.versions.append(version)

            if verbose:
                print(f"📝 Version {version.version} created: {new_word_count} words")

            self.generation_log.append(
                f"Version {version.version}: Improved article ({new_word_count} words, targeting {improvement_analysis['focus_summary']})"
            )

            current_article = improved_article

        # Final scoring
        # prediction = self.judge.forward(current_article)
        final_score_results = score_results
        final_word_count = (
            final_score_results.word_count
            or self.word_count_manager.count_words(current_article)
        )
        final_length_status = self.word_count_manager.get_word_count_status(
            final_word_count
        )

        if self.versions:
            self.versions[-1].score_results = final_score_results

        # Prepare final result with combined target achievement
        final_quality_achieved = (
            final_score_results.percentage >= self.target_score_percentage
        )
        final_length_achieved = final_length_status["within_range"]
        both_targets_achieved = final_quality_achieved and final_length_achieved

        final_result = {
            "final_article": current_article,
            "final_score": final_score_results,
            "target_achieved": both_targets_achieved,
            "quality_achieved": final_quality_achieved,
            "length_achieved": final_length_achieved,
            "iterations_used": iteration,
            "versions": self.versions,
            "generation_log": self.generation_log,
            "word_count": final_word_count,
            "improvement_summary": self._generate_improvement_summary(),
        }

        return final_result

    def _generate_initial_article(
        self, draft_or_outline: str, context: Dict[str, str], verbose: bool
    ) -> str:
        """Generate initial markdown article from draft/outline using ArticleGenerationSignature."""

        # Always perform RAG search for comprehensive context
        if verbose:
            print("🌐 Performing comprehensive RAG search...")

        final_context = self._perform_rag_search(draft_or_outline, verbose)

        if verbose and final_context:
            print(f"📚 Using context: {len(final_context)}")

        # Prepare generation inputs
        scoring_criteria = self.criteria_extractor.get_criteria_for_generation()
        word_count_guidance = self.word_count_manager.get_length_optimization_prompt(
            self.word_count_manager.target_optimal
        )

        try:
            # Validate context window before generation
            context_str = str(final_context) if final_context else ""
            content_parts = {
                "draft": draft_or_outline,
                "context": context_str,
                "criteria": scoring_criteria,
                "guidance": word_count_guidance,
            }

            try:
                self.context_manager.validate_content(content_parts)
            except ContextWindowError as e:
                if verbose:
                    print(f"⚠️ Context window validation failed: {e}")
                # Reduce context size and retry
                final_context = {}
                context_str = ""
                content_parts["context"] = ""
                self.context_manager.validate_content(content_parts)

            # Generate initial article with comprehensive RAG context
            with dspy.context(lm=self.models["generator"].dspy_lm):
                result = self.generator(
                    original_draft=draft_or_outline,
                    context=final_context,
                    scoring_criteria=scoring_criteria,
                    word_count_guidance=word_count_guidance,
                )

            return result.generated_article

        except Exception as e:
            if verbose:
                print(f"⚠️ Initial generation failed, using draft as fallback: {e}")

            # Fallback to original draft if generation fails
            return draft_or_outline

    def _analyze_improvement_needs(
        self, score_results: ArticleScoreModel, current_article: str
    ) -> Dict[str, Any]:
        """Analyze what improvements are needed based on scoring results."""

        # Get improvement guidelines from criteria extractor
        improvement_guidelines = self.criteria_extractor.get_improvement_guidelines(
            score_results
        )

        # Get gap analysis
        gap_analysis = self.criteria_extractor.analyze_score_gaps(
            score_results, self.target_score_percentage
        )

        # Get word count analysis
        word_count = self.word_count_manager.count_words(current_article)
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
            score_results, gap_analysis, length_analysis, improvement_guidelines
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
    ) -> str:
        """Generate comprehensive feedback for improvement."""

        feedback_parts = []

        # Current performance summary
        feedback_parts.append("CURRENT PERFORMANCE ANALYSIS:")
        feedback_parts.append(
            f"Score: {score_results.total_score}/{self.criteria_extractor.get_total_possible_score()} ({score_results.percentage:.1f}%)"
        )
        feedback_parts.append(f"Gap to target: {gap_analysis['total_gap']} points")
        feedback_parts.append("")

        # Priority improvement areas
        if gap_analysis["priority_categories"]:
            feedback_parts.append("TOP PRIORITY IMPROVEMENTS:")
            for i, cat_info in enumerate(gap_analysis["priority_categories"][:3], 1):
                category = cat_info["category"]
                gap = cat_info["gap"]
                weight = cat_info["weight"]
                feedback_parts.append(
                    f"{i}. {category}: +{gap} points needed (category weight: {weight})"
                )
            feedback_parts.append("")

        # Length vs quality strategy
        feedback_parts.append("LENGTH & QUALITY STRATEGY:")
        feedback_parts.append(f"Primary focus: {length_analysis['strategy']}")
        feedback_parts.append(f"Risk level: {length_analysis['risk_level']}")
        feedback_parts.append("")

        # Specific improvement guidelines
        feedback_parts.append(improvement_guidelines)

        return "\n".join(feedback_parts)

    def _generate_improved_version(
        self,
        current_article: str,
        score_results: ArticleScoreModel,
        improvement_analysis: Dict[str, Any],
        verbose: bool = False,
    ) -> str:
        """Generate an improved version of the article while maintaining consistency with original draft."""

        # Perform fresh RAG search for improvement context
        # This ensures we get updated/additional context for each iteration
        # Always perform RAG search for comprehensive context
        if verbose:
            print("🌐 Performing comprehensive RAG search...")

        context = self._perform_rag_search(current_article, verbose=verbose)

        if verbose and context:
            print(f"📚 Using context: {len(context)}")

        # Prepare improvement inputs
        scoring_criteria = self.criteria_extractor.get_criteria_for_generation()
        word_count_guidance = self.word_count_manager.get_length_optimization_prompt(
            self.word_count_manager.count_words(current_article), score_results
        )

        try:
            # Validate context window before improvement
            context_str = str(context) if context else ""
            content_parts = {
                "current_article": current_article,
                "original_draft": self._get_original_draft(),
                "context": context_str,
                "feedback": improvement_analysis["detailed_feedback"],
                "criteria": scoring_criteria,
                "guidance": word_count_guidance,
                "focus": improvement_analysis["focus_summary"],
            }

            try:
                self.context_manager.validate_content(content_parts)
            except ContextWindowError as e:
                print(f"⚠️ Context window validation failed for improvement: {e}")
                # Reduce context size and retry
                combined_context = {}
                context_str = ""
                content_parts["context"] = ""
                self.context_manager.validate_content(content_parts)

            # Generate improved article with comprehensive RAG context
            with dspy.context(lm=self.models["generator"].dspy_lm):
                result = self.improver(
                    current_article=current_article,
                    original_draft=self._get_original_draft(),
                    context=context,
                    score_feedback=improvement_analysis["detailed_feedback"],
                    scoring_criteria=scoring_criteria,
                    word_count_guidance=word_count_guidance,
                    improvement_focus=improvement_analysis["focus_summary"],
                )

            return result.improved_article

        except Exception as e:
            print(f"⚠️ Improvement generation failed, returning current article: {e}")
            return current_article

    def _get_original_draft(self) -> str:
        """Get the original draft for reference during improvements."""
        return self.original_draft or ""

    def _generate_improvement_summary(self) -> Dict[str, Any]:
        """Generate a summary of the improvement process."""
        if len(self.versions) < 2:
            return {"message": "No improvements made"}

        initial_version = self.versions[0]
        final_version = self.versions[-1]

        initial_score = (
            initial_version.score_results.percentage
            if initial_version.score_results
            else 0
        )
        final_score = (
            final_version.score_results.percentage if final_version.score_results else 0
        )

        word_count_change = final_version.word_count - initial_version.word_count

        return {
            "initial_score": initial_score,
            "final_score": final_score,
            "score_improvement": final_score - initial_score,
            "initial_word_count": initial_version.word_count,
            "final_word_count": final_version.word_count,
            "word_count_change": word_count_change,
            "versions_created": len(self.versions),
            "target_achieved": final_score >= self.target_score_percentage,
        }

    def _print_final_summary(self, final_result: Dict[str, Any]):
        """Print a comprehensive final summary."""
        print("\n" + "=" * 60)
        print("🏆 FINAL RESULTS")
        print("=" * 60)

        final_score = final_result["final_score"]
        improvement_summary = final_result["improvement_summary"]

        print(
            f"📊 Final Score: {final_score.total_score}/{self.criteria_extractor.get_total_possible_score()} ({final_score.percentage:.1f}%)"
        )
        print(f"🎯 Target: ≥{self.target_score_percentage}%")
        print(
            f"✅ Target Achieved: {'YES' if final_result['target_achieved'] else 'NO'}"
        )
        print(
            f"🔄 Iterations Used: {final_result['iterations_used']}/{self.max_iterations}"
        )
        print(f"📝 Final Word Count: {final_result['word_count']} words")

        if len(self.versions) > 1:
            print(
                f"📈 Score Improvement: +{improvement_summary['score_improvement']:.1f}%"
            )
            print(
                f"📏 Word Count Change: {improvement_summary['word_count_change']:+d} words"
            )

        print("\n📋 GENERATION LOG:")
        for log_entry in self.generation_log:
            print(f"  • {log_entry}")

        if final_result["target_achieved"]:
            print("\n🎉 CONGRATULATIONS! Your article has achieved world-class status!")
        else:
            print(
                f"\n💡 Continue improving to reach the {self.target_score_percentage}% target."
            )

    def get_version_history(self) -> List[Dict[str, Any]]:
        """Get a summary of all article versions."""
        history = []

        for version in self.versions:
            version_info = {
                "version": version.version,
                "word_count": version.word_count,
                "timestamp": version.timestamp,
                "improvement_feedback": version.improvement_feedback,
            }

            if version.score_results:
                version_info.update(
                    {
                        "score": version.score_results.total_score,
                        "percentage": version.score_results.percentage,
                        "category_scores": {
                            category: sum(r.score for r in results)
                            for category, results in version.score_results.category_scores.items()
                        },
                    }
                )

            history.append(version_info)

        return history

    def export_results(self, filepath: str):
        """Export generation results to JSON file."""
        if not self.versions:
            raise ValueError("No generation results to export")

        export_data = {
            "target_score_percentage": self.target_score_percentage,
            "final_achieved": (
                self.versions[-1].score_results.percentage
                >= self.target_score_percentage
                if self.versions[-1].score_results
                else False
            ),
            "generation_log": self.generation_log,
            "version_history": self.get_version_history(),
            "final_article": self.versions[-1].content,
            "final_score_details": (
                self.versions[-1].score_results.model_dump()
                if self.versions[-1].score_results
                else None
            ),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    print("This module is intended to be imported and used within other scripts.")
