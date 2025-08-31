#!/usr/bin/env python3
"""
LinkedIn Article Generator

Main orchestrator class that implements the iterative article generation and improvement
process using DSPy, scoring criteria, and word count management.
"""

import dspy
from typing import Dict, Any, List, Optional, Tuple
import json
import time
import re
import asyncio

from models import ArticleVersion, JudgementModel
from li_judge_simple import ComprehensiveLinkedInArticleJudge
from li_judge_simple import get_criteria_for_generation
from word_count_manager import WordCountManager
from dspy_factory import DspyModelConfig
from context_window_manager import ContextWindowManager, ContextWindowError
from rag_fast import retrieve_and_pack


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

    class VerboseManager:
        """Centralized manager for beautiful, structured verbose output."""

        def __init__(self, generator_instance):
            self.generator = generator_instance

        def print_section_header(self, title: str, emoji: str = "📋"):
            """Print a formatted section header with borders."""
            border = "=" * 60
            print(f"\n{border}")
            print(f"{emoji} {title.upper()}")
            print(f"{border}")

        def print_generation_start(self):
            """Print beautiful generation start header with all key parameters."""
            self.print_section_header("LinkedIn Article Generation Process", "🚀")

            print("📊 CONFIGURATION PARAMETERS:")
            print(f"  • Target Score: ≥{self.generator.target_score_percentage}%")
            print(f"  • Max Iterations: {self.generator.max_iterations}")
            print(
                f"  • Word Count Range: {self.generator.word_count_manager.target_min}-{self.generator.word_count_manager.target_max}"
            )
            print(f"  • Generator Model: {self.generator.models['generator'].name}")
            print(f"  • Judge Model: {self.generator.models['judge'].name}")
            print(f"  • RAG Model: {self.generator.models['rag'].name}")
            print(f"  • Recreate Context: {self.generator.recreate_ctx}")

        def print_iteration_status(self, iteration: int, version: "ArticleVersion"):
            """Print rich iteration status with scores and metrics."""
            print(f"\n🔄 ITERATION {iteration}: SCORING AND ANALYSIS")
            print("-" * 50)

            judgement = version.judgement
            print("📊 CURRENT STATUS:")
            print(f"  • Version: {version.version}")
            print(f"  • Word Count: {judgement.word_count} words")
            print(
                f"  • Score: {judgement.total_score}/{judgement.max_score} ({judgement.percentage:.1f}%)"
            )
            print(f"  • Target: ≥{self.generator.target_score_percentage}%")
            print(
                f"  • Target Range: {self.generator.word_count_manager.target_min}-{self.generator.word_count_manager.target_max}"
            )

            if judgement.improvement_prompt:
                print(f"\n🔍 IMPROVEMENT GUIDANCE:")
                print(f"  {judgement.improvement_prompt}")

            if judgement.focus_areas:
                print(f"\n🎯 FOCUS AREAS:")
                print(f"  {judgement.focus_areas}")

        def print_rag_status(
            self, context_length: int, urls: Optional[List[str]] = None
        ):
            """Print RAG search results and context information."""
            print("🌐 RAG SEARCH RESULTS:")
            if context_length > 0:
                print(f"  ✅ Retrieved context: {context_length} characters")
                if urls:
                    print(f"  📚 Source URLs: {len(urls)} found")
                    for i, url in enumerate(urls[:3], 1):  # Show first 3 URLs
                        print(f"    {i}. {url}")
                    if len(urls) > 3:
                        print(f"    ... and {len(urls) - 3} more")
                else:
                    print("  📚 Source URLs: None specified")
            else:
                print("  ⚠️ No context retrieved from RAG search")

        def print_context_reuse(self, context_length: int, recreate_ctx: bool):
            """Print context reuse or fresh search status."""
            if recreate_ctx:
                print("🌐 CONTEXT STRATEGY:")
                print("  🔄 Performing fresh RAG search (recreate_ctx=True)")
            else:
                print("🌐 CONTEXT STRATEGY:")
                print(f"  🔄 Reusing initial context: {context_length} characters")
                print("  📋 recreate_ctx=False - maintaining consistency")

        def print_generation_phase(self, phase: str, details: str = ""):
            """Print generation phase status."""
            print(f"\n📝 {phase.upper()}")
            if details:
                print(f"  {details}")

        def print_final_summary(self, final_result: Dict[str, Any]):
            """Print comprehensive final summary with all metrics."""
            self.print_section_header("Final Results", "🏆")

            final_score = final_result["final_score"]
            improvement_summary = final_result["improvement_summary"]

            print("📊 FINAL METRICS:")
            print(
                f"  • Final Score: {final_score.total_score}/{final_score.max_score} ({final_score.percentage:.1f}%)"
            )
            print(f"  • Target Score: ≥{self.generator.target_score_percentage}%")
            print(
                f"  • Target Achieved: {'✅ YES' if final_result['target_achieved'] else '❌ NO'}"
            )
            print(
                f"  • Quality Achieved: {'✅ YES' if final_result['quality_achieved'] else '❌ NO'}"
            )
            print(
                f"  • Length Achieved: {'✅ YES' if final_result['length_achieved'] else '❌ NO'}"
            )
            print(
                f"  • Iterations Used: {final_result['iterations_used']}/{self.generator.max_iterations}"
            )
            print(f"  • Final Word Count: {final_result['word_count']} words")

            if len(self.generator.versions) > 1:
                print("\n📈 IMPROVEMENT SUMMARY:")
                print(
                    f"  • Score Improvement: +{improvement_summary['score_improvement']:.1f}%"
                )
                print(
                    f"  • Word Count Change: {improvement_summary['word_count_change']:+d} words"
                )
                print(
                    f"  • Versions Created: {improvement_summary['versions_created']}"
                )

            print("\n📋 GENERATION LOG:")
            for log_entry in final_result["generation_log"]:
                print(f"  • {log_entry}")

            if final_result["target_achieved"]:
                print("\n🎉 SUCCESS! Article achieved world-class status!")
            else:
                print(
                    f"\n💡 Continue improving to reach the {self.generator.target_score_percentage}% target."
                )

        def print_variable_dump(
            self, variables: Dict[str, Any], title: str = "Variable Dump"
        ):
            """Print debug dump of key variables."""
            print(f"\n🔧 {title.upper()}")
            print("-" * 40)
            for key, value in variables.items():
                if isinstance(value, (int, float)):
                    print(f"  • {key}: {value}")
                elif isinstance(value, str) and len(value) > 100:
                    print(f"  • {key}: {value[:100]}... (truncated)")
                else:
                    print(f"  • {key}: {value}")

    def __init__(
        self,
        target_score_percentage: float,
        max_iterations: int,
        word_count_min: int,
        word_count_max: int,
        models: Dict[str, DspyModelConfig],
        recreate_ctx: bool = False,
        auto: bool = False,
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

        # Initialize VerboseManager for beautiful verbose output
        self.verbose_manager = self.VerboseManager(self)

        # Store model preferences
        self.models = models

        # Initialize context window manager
        self.context_manager = ContextWindowManager(models["generator"])

        # Use the new comprehensive judge with encapsulated analysis logic
        self.judge = ComprehensiveLinkedInArticleJudge(
            models=models,
            min_length=word_count_min,
            max_length=word_count_max,
            passing_score_percentage=target_score_percentage,
        )

        self.word_count_manager = WordCountManager(word_count_min, word_count_max)

        # Initialize DSPy modules with optional model-specific LM instances

        self.generator = dspy.ChainOfThought(ArticleGenerationSignature)
        self.improver = dspy.ChainOfThought(ArticleImprovementSignature)

        # Track generation history
        self.versions: List[ArticleVersion] = []
        self.generation_log: List[str] = []
        self.original_draft: Optional[str] = None
        self.recreate_ctx = recreate_ctx
        self.auto = auto

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
                self.verbose_manager.print_rag_status(len(ctx), urls)

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
            self.verbose_manager.print_generation_start()

        # Clear previous generation data
        self.versions.clear()
        self.generation_log.clear()
        self.original_draft = initial_draft
        self.search_context = context or {}

        if context and verbose:
            print(f"🌐 Using web context: {len(context)} URLs")

        # Generate initial markdown article from draft/outline (Version 1)
        if verbose:
            self.verbose_manager.print_generation_phase(
                "Generating initial markdown article from draft"
            )

        initial_article, initial_context = self._generate_initial_article(
            initial_draft, context, verbose
        )

        # Start iterative improvement process with the generated article
        final_result = self._iterative_improvement_process(
            initial_article, initial_context, verbose
        )

        if verbose:
            self.verbose_manager.print_final_summary(final_result)

        return final_result

    def _iterative_improvement_process(
        self, initial_article: str, initial_context: str, verbose: bool
    ) -> Dict[str, Any]:
        """Run the iterative improvement process with user interaction and combined quality and length validation."""
        current_article = initial_article
        current_context = initial_context
        iteration = 0
        user_instructions = ""  # Track user-provided instructions

        # Ensure at least one iteration runs to get a judgement
        while iteration < max(1, self.max_iterations):
            iteration += 1

            # Print article version before judging
            if verbose:
                self._print_article_version_before_judging(current_article, iteration)

            # Create a pending judgement for the temporary version
            pending_judgement = JudgementModel(
                total_score=0,
                max_score=100,
                percentage=0.0,
                performance_tier="Pending",
                word_count=len(current_article.split()),  # Quick word count estimate
                meets_requirements=False,
                improvement_prompt="Pending analysis - this is a temporary placeholder that will be replaced with actual improvement guidance from the comprehensive judge.",
                focus_areas="Pending analysis - temporary placeholder for focus areas",
                overall_feedback=None,  # Optional field for comprehensive feedback
            )

            # Create a temporary version for judging
            temp_version = ArticleVersion(
                version=iteration,
                content=current_article,
                context=current_context,
                recreate_ctx=self.recreate_ctx,
                judgement=pending_judgement,  # Pending placeholder
            )

            # Judge with the temporary version included
            prediction = self.judge(self.versions + [temp_version])
            judgement = prediction.output  # This is the real judgement

            # Now create the final version with the actual judgement
            version = ArticleVersion(
                version=iteration,
                content=current_article,
                context=current_context,
                recreate_ctx=self.recreate_ctx,
                judgement=judgement,  # Real judgement from the judge
            )
            self.versions.append(version)

            # Print judging results after judging
            if verbose:
                self._print_judging_results_after_judging(version)

            self.generation_log.append(
                f"Version {version.version}: Improved article ({version.judgement.word_count} words, improvement {version.judgement.improvement_prompt})"
            )

            if self.auto == False:
                # In non-auto mode, always print iteration status
                self.verbose_manager.print_iteration_status(iteration, version)

                user_decision = self._get_user_decision(version)
                if user_decision == "finish":
                    break
                elif user_decision == "continue":
                    user_instructions = self._get_user_instructions()
                    # Prepend user instructions to judge's improvement prompt if provided
                    if user_instructions:
                        judgement.improvement_prompt = f"""THESE ARE NEW INSTRUCTIONS:
<NEW>
{user_instructions}
<NEW/>

{judgement.improvement_prompt}"""
            else:

                # Check if targets are achieved using the judge's decision
                if version.judgement.meets_requirements:
                    if verbose:
                        print(
                            f"🎉 BOTH TARGETS ACHIEVED! Article reached world-class status with optimal length!"
                        )

                    self.generation_log.append(
                        f"Iteration {iteration}: Both targets achieved (Score: {version.judgement.percentage:.1f}%, Words: {version.judgement.word_count})"
                    )
                    break  # Exit loop if both targets are met

                else:
                    if verbose:
                        print(f"⚠️ Targets not yet achieved: {judgement.focus_areas}")

            # Generate improved version using the judge's improvement prompt
            if verbose:
                self.verbose_manager.print_generation_phase(
                    "Generating improved version"
                )

            improved_article, used_context = (
                self._generate_improved_version_with_judgement(
                    current_article, judgement, verbose
                )
            )

            current_article = improved_article
            current_context = used_context

        # Final scoring
        final_judgement = self.versions[-1].judgement
        final_word_count = (
            final_judgement.word_count
            or self.word_count_manager.count_words(current_article)
        )
        final_length_status = self.word_count_manager.get_word_count_status(
            final_word_count
        )

        if self.versions:
            self.versions[-1].judgement = final_judgement

        # Prepare final result with combined target achievement
        final_quality_achieved = (
            final_judgement.percentage >= self.target_score_percentage
        )
        final_length_achieved = final_length_status["within_range"]
        both_targets_achieved = final_quality_achieved and final_length_achieved

        final_result = {
            "final_article": current_article,
            "final_score": final_judgement,
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
    ) -> Tuple[str, str]:
        """Generate initial markdown article from draft/outline using ArticleGenerationSignature.

        Returns:
            Tuple of (generated_article, context_used)
        """

        # Always perform RAG search for comprehensive context
        if verbose:
            self.verbose_manager.print_generation_phase(
                "Performing comprehensive RAG search"
            )

        final_context = self._perform_rag_search(draft_or_outline, verbose)

        if verbose and final_context:
            print(f"📚 Using context: {len(final_context)} characters")

        # Prepare generation inputs
        scoring_criteria = get_criteria_for_generation()
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
                final_context = ""
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

            return result.generated_article, final_context

        except Exception as e:
            if verbose:
                print(f"⚠️ Initial generation failed, using draft as fallback: {e}")

            # Fallback to original draft if generation fails
            return draft_or_outline, final_context or ""

    def _generate_improved_version_with_judgement(
        self, current_article: str, judgement: JudgementModel, verbose: bool = False
    ) -> Tuple[str, str]:
        """Generate an improved version using the judge's improvement prompt.

        Returns:
            Tuple of (improved_article, context_used)
        """

        # Determine context based on recreate_ctx flag
        if self.recreate_ctx:
            # Perform fresh RAG search for improvement context
            context = self._perform_rag_search(current_article, verbose=verbose)
            if verbose:
                self.verbose_manager.print_context_reuse(len(context), True)
        else:
            # Reuse context from the first version
            if self.versions and len(self.versions) > 0:
                context = self.versions[0].context
                if verbose:
                    self.verbose_manager.print_context_reuse(len(context), False)
            else:
                # Fallback if no versions exist yet
                if verbose:
                    print("⚠️ No initial context available, performing fresh search...")
                context = self._perform_rag_search(current_article, verbose=verbose)

        if verbose and context:
            print(f"📚 Using context: {len(context)} characters")

        # Prepare improvement inputs using judge's guidance
        scoring_criteria = get_criteria_for_generation()
        word_count_guidance = self.word_count_manager.get_length_optimization_prompt(
            judgement.word_count
        )

        try:
            # Validate context window before improvement
            context_str = str(context) if context else ""
            content_parts = {
                "current_article": current_article,
                "original_draft": self._get_original_draft(),
                "context": context_str,
                "feedback": judgement.improvement_prompt,
                "criteria": scoring_criteria,
                "guidance": word_count_guidance,
                "focus": judgement.focus_areas,
            }

            try:
                self.context_manager.validate_content(content_parts)
            except ContextWindowError as e:
                if verbose:
                    print(f"⚠️ Context window validation failed for improvement: {e}")
                # Reduce context size and retry
                context_str = ""
                content_parts["context"] = ""
                self.context_manager.validate_content(content_parts)

            # Generate improved article using judge's improvement prompt
            with dspy.context(lm=self.models["generator"].dspy_lm):
                result = self.improver(
                    current_article=current_article,
                    original_draft=self._get_original_draft(),
                    context=context,
                    score_feedback=judgement.improvement_prompt,
                    scoring_criteria=scoring_criteria,
                    word_count_guidance=word_count_guidance,
                    improvement_focus=judgement.focus_areas,
                )

            return result.improved_article, context

        except Exception as e:
            if verbose:
                print(
                    f"⚠️ Improvement generation failed, returning current article: {e}"
                )
            return current_article, context or ""

    def _get_original_draft(self) -> str:
        """Get the original draft for reference during improvements."""
        return self.original_draft or ""

    def _print_article_version_before_judging(
        self, article_content: str, version_number: int
    ):
        """Print the article version content before sending it to be judged."""
        print(f"\n📄 ARTICLE VERSION {version_number} - SENDING TO JUDGE")
        print("=" * 60)
        print("Article Content:")
        print("-" * 30)
        # Print first 500 characters to avoid overwhelming output
        preview = article_content[:500]
        print(preview)
        if len(article_content) > 500:
            print(f"\n[... {len(article_content) - 500} more characters ...]")
        print("=" * 60)

    def _print_judging_results_after_judging(self, version: "ArticleVersion"):
        """Print comprehensive judging results after evaluation."""
        judgement = version.judgement
        print(f"\n🎯 JUDGING RESULTS FOR VERSION {version.version}")
        print("=" * 60)
        print("📊 SCORES:")
        print(f"  • Total Score: {judgement.total_score}/{judgement.max_score}")
        print(f"  • Percentage: {judgement.percentage:.1f}%")
        print(f"  • Performance Tier: {judgement.performance_tier}")
        print(f"  • Word Count: {judgement.word_count} words")
        print(
            f"  • Meets Requirements: {'✅ YES' if judgement.meets_requirements else '❌ NO'}"
        )

        if judgement.overall_feedback:
            print("\n💬 OVERALL FEEDBACK:")
            print(f"  {judgement.overall_feedback}")

        if judgement.improvement_prompt:
            print("\n🔧 IMPROVEMENT PROMPT:")
            print(f"  {judgement.improvement_prompt}")

        if judgement.focus_areas:
            print("\n🎯 FOCUS AREAS:")
            print(f"  {judgement.focus_areas}")

        print("=" * 60)

    def _get_user_decision(self, version: "ArticleVersion") -> str:
        """Ask user whether to continue improving or finish."""
        print("\n🤔 USER DECISION TIME")
        print("-" * 30)
        print(f"Version {version.version} has been evaluated.")
        print("Choose your next action:")
        print("  1. finish - Accept this version as final")
        print("  2. continue - Generate another improved version")

        while True:
            try:
                choice = input("Enter your choice (1 or 2): ").strip().lower()
                if choice in ["1", "finish", "f"]:
                    return "finish"
                elif choice in ["2", "continue", "c"]:
                    return "continue"
                else:
                    print("Please enter '1', 'finish', '2', or 'continue'")
            except KeyboardInterrupt:
                print("\nOperation cancelled by user.")
                return "finish"

    def _get_user_instructions(self) -> str:
        """Ask user for new instructions to add to the improvement prompt."""
        print("\n📝 NEW INSTRUCTIONS")
        print("-" * 30)
        print("Enter any specific instructions for improving the next version.")
        print("These will be added to the beginning of the improvement prompt.")
        print("(Press Enter with no text to skip)")

        try:
            instructions = input("Your instructions: ").strip()
            if instructions:
                print(
                    f"\n✅ Instructions added: {instructions[:100]}{'...' if len(instructions) > 100 else ''}"
                )
            else:
                print(
                    "\n⏭️ No instructions provided - proceeding without additional guidance"
                )
            return instructions
        except KeyboardInterrupt:
            print(
                "\n⏭️ Operation cancelled - proceeding without additional instructions"
            )
            return ""

    def _generate_improvement_summary(self) -> Dict[str, Any]:
        """Generate a summary of the improvement process."""
        if len(self.versions) < 2:
            return {"message": "No improvements made"}

        initial_version = self.versions[0]
        final_version = self.versions[-1]

        initial_score = (
            initial_version.judgement.percentage if initial_version.judgement else 0
        )
        final_score = (
            final_version.judgement.percentage if final_version.judgement else 0
        )

        word_count_change = (
            final_version.judgement.word_count - initial_version.judgement.word_count
        )

        return {
            "initial_score": initial_score,
            "final_score": final_score,
            "score_improvement": final_score - initial_score,
            "initial_word_count": initial_version.judgement.word_count,
            "final_word_count": final_version.judgement.word_count,
            "word_count_change": word_count_change,
            "versions_created": len(self.versions),
            "target_achieved": final_score >= self.target_score_percentage,
        }

    def _print_final_summary(self, final_result: Dict[str, Any]):
        """Print a comprehensive final summary using VerboseManager."""
        self.verbose_manager.print_final_summary(final_result)

    def get_version_history(self) -> List[Dict[str, Any]]:
        """Get a summary of all article versions."""
        history = []

        for version in self.versions:
            version_info = {
                "version": version.version,
                "word_count": version.judgement.word_count,
                "timestamp": version.timestamp,
                "improvement_feedback": version.judgement.improvement_prompt,
            }

            if version.judgement:
                version_info.update(
                    {
                        "score": version.judgement.total_score,
                        "percentage": version.judgement.percentage,
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
                self.versions[-1].judgement.percentage >= self.target_score_percentage
                if self.versions[-1].judgement
                else False
            ),
            "generation_log": self.generation_log,
            "version_history": self.get_version_history(),
            "final_article": self.versions[-1].content,
            "final_score_details": (
                self.versions[-1].judgement.model_dump()
                if self.versions[-1].judgement
                else None
            ),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    print("This module is intended to be imported and used within other scripts.")
