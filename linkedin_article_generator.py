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
import os
from pathlib import Path
import traceback


from models import ArticleVersion, JudgementModel
from li_article_judge import ComprehensiveLinkedInArticleJudge, CriteriaExtractor
from word_count_manager import WordCountManager
from dspy_factory import DspyModelConfig
from context_window_manager import ContextWindowManager, ContextWindowError
from rag_fast import retrieve_and_pack
from progress_dashboard import ProgressDashboard, UserInteractionManager


class ArticleGenerationSignature(dspy.Signature):
    """Generate a complete LinkedIn article in markdown format with these requirements:

    WORD LENGTH REQUIREMENT:
    - The top priority is to to generate an article of the wanted length range
    - If expansion is needed, focus on areas that improve both length and quality
    - If condensation is needed, preserve all key insights and arguments
    - Use the scoring criteria to strategically adjust content length while maintaining article quality

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

    CONTENT REQUIREMENTS:
    - Expand the draft/outline into a comprehensive LinkedIn article
    - Maintain professional LinkedIn tone and structure
    - Objective and third-person, with a more structured, business/technical tone
    - Address all key points from the original draft"""

    original_draft: str = dspy.InputField(
        desc="Original draft to expand on key points if necessary",
    )
    context: str = dspy.InputField(
        desc="String containing relevant content with inline markdown citations already formatted. Citations appear as [specific claim or data point](source_url) within the text.",
        default="",
    )
    scoring_criteria: str = dspy.InputField(
        desc="Complete scoring criteria for reference"
    )
    generated_article: str = dspy.OutputField(
        desc="""The generated LinkedIn article in markdown format meeting all the above requirements."""
    )


class ArticleImprovementSignature(dspy.Signature):
    """Improve an existing article based on scoring feedback and criteria while maintaining consistency with original draft.
    WORD LENGTH REQUIREMENT:
    - The top priority is to to generate an article of the wanted length range
    - If expansion is needed, focus on areas that improve both length and quality
    - If condensation is needed, preserve all key insights and arguments
    - Use the scoring criteria to strategically adjust content length while maintaining article quality

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

    CONTENT REQUIREMENTS:
    - Expand the draft/outline into a comprehensive LinkedIn article
    - Maintain professional LinkedIn tone and structure
    - Objective and third-person, with a more structured, business/technical tone
    - Address all key points from the original draft"""

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

    improved_article = dspy.OutputField(
        desc="The improved article meeting all the above requirements."
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

            if judgement.improvement_prompt:
                print(f"\n🔍 IMPROVEMENT GUIDANCE:")
                print(f"  {judgement.improvement_prompt}")

            print(f"  • Version: {version.version}")
            print(
                f"  • Score: {judgement.total_score}/{judgement.max_score} ({judgement.percentage:.1f}%)"
            )
            print(f"  • Target: ≥{self.generator.target_score_percentage}%")
            print(f"  • Word Count: {judgement.word_count} words")
            print(
                f"  • Target Range: {self.generator.word_count_manager.target_min}-{self.generator.word_count_manager.target_max}"
            )

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
        export_dir: Optional[str] = None,
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

        # Initialize progress dashboard and user interaction manager
        self.dashboard = ProgressDashboard()
        self.interaction_manager = UserInteractionManager(self.dashboard)

        # Store model preferences
        self.models = models

        # Initialize context window manager
        self.context_manager = ContextWindowManager(models["generator"])

        # Use the new A vs. B judge with encapsulated analysis logic
        self.judge = ComprehensiveLinkedInArticleJudge(
            models=models,
            min_length=word_count_min,
            max_length=word_count_max,
            passing_score_percentage=target_score_percentage,
        )
        self.criteria_extractor = CriteriaExtractor(
            min_length=word_count_min, max_length=word_count_max
        )

        self.word_count_manager = WordCountManager(word_count_min, word_count_max)

        # Initialize DSPy modules with optional model-specific LM instances

        self.generator = dspy.ChainOfThought(ArticleGenerationSignature)
        self.improver = dspy.ChainOfThought(ArticleImprovementSignature)

        # Track generation history
        self.iteration = 0
        self.versions: List[ArticleVersion] = []
        self.generation_log: List[str] = []
        self.original_draft: Optional[str] = None
        self.recreate_ctx = recreate_ctx
        self.auto = auto

        if export_dir:
            # Use command-line specified directory with automatic numbering
            export_dir = self._resolve_directory_name(export_dir)
            print(f"📁 Using directory: {export_dir}")
        self.export_dir = export_dir

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
        return self.generate_article_with_context(initial_draft, "", verbose)

    def generate_article_with_context(
        self, initial_draft: str, context: str = "", verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a world-class LinkedIn article from a draft or outline with web context.

        Args:
            initial_draft: Initial draft article or outline
            context: String containing relevant content with inline citations
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
        self.search_context = context or ""

        if context and verbose:
            print(f"🌐 Using web context: {len(context)} URLs")

        if verbose:
            self.verbose_manager.print_generation_phase(
                "Generating initial markdown article from draft"
            )

        initial_article, initial_context = self._generate_initial_article(
            initial_draft, context, verbose
        )

        # Store draft version with a pending judgement
        draft_judgement = JudgementModel(
            total_score=0,
            max_score=100,
            percentage=0.0,
            performance_tier="User provided draft",
            word_count=self.word_count_manager.count_words(initial_draft),
            meets_requirements=False,
            improvement_prompt="There is no improvement guidance since this is the user-provided draft, that will not be judged.",
            overall_feedback=None,  # Optional field for comprehensive feedback
        )

        # Create a temporary version for judging
        draft_version = ArticleVersion(
            version=self.iteration,
            content=initial_draft,
            context=initial_context,
            recreate_ctx=self.recreate_ctx,
            judgement=draft_judgement,
        )

        self.versions.append(draft_version)

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
        user_instructions = ""  # Track user-provided instructions
        finish_requested = False  # Track if user requested to finish early

        try:
            # Ensure at least one iteration runs to get a judgement
            while self.iteration < max(1, self.max_iterations):
                self.iteration += 1

                word_count = self.word_count_manager.count_words(current_article)

                # Print article version before judging
                if verbose:
                    self._print_article_version_before_judging(
                        current_article, self.iteration, word_count
                    )

                # Create a pending judgement for the temporary version
                pending_judgement = JudgementModel(
                    total_score=0,
                    max_score=100,
                    percentage=0.0,
                    performance_tier="Pending",
                    word_count=word_count,
                    meets_requirements=False,
                    improvement_prompt="Pending analysis - this is a temporary placeholder that will be replaced with actual improvement guidance from the comprehensive judge.",
                    overall_feedback=None,  # Optional field for comprehensive feedback
                )

                # Create a temporary version for judging
                temp_version = ArticleVersion(
                    version=self.iteration,
                    content=current_article,
                    context=current_context,
                    recreate_ctx=self.recreate_ctx,
                    judgement=pending_judgement,  # Pending placeholder
                )

                # Judge with the temporary version included
                prediction = self.judge(self.versions + [temp_version])

                # Judged version to append
                version = prediction.output  # This is the real judgement
                judgement = version.judgement
                self.versions.append(version)

                # Print judging results after judging
                if verbose:
                    self._print_judging_results_after_judging(version)

                self.generation_log.append(
                    f"Version {version.version}: Improved article ({version.judgement.word_count} words, improvement {version.judgement.improvement_prompt})"
                )

                if self.auto == False:
                    # In non-auto mode, always print iteration status
                    self.verbose_manager.print_iteration_status(self.iteration, version)

                    keep_asking = True
                    while keep_asking:

                        user_decision = self._get_user_decision(version)

                        if user_decision == "finish":
                            keep_asking = False  # Default to not asking again
                            # break out of loop while self.iteration < max(1, self.max_iterations): to finish
                            if verbose:
                                print("🏁 User chose to finish the generation process.")
                            finish_requested = True

                        elif user_decision == "instructions":
                            keep_asking = False
                            user_instructions = self._get_user_instructions()
                            # Prepend user instructions to judge's improvement prompt if provided
                            if user_instructions:
                                judgement.improvement_prompt = f"""THESE ARE NEW INSTRUCTIONS:
    <NEW>
    {user_instructions}
    <NEW/>"""
                        elif user_decision == "export":
                            self._export_version_to_directory(self.export_dir)
                            continue  # Return to menu after export
                        # Continue with improvement if "continue" or "instructions" was selected
                        elif user_decision == "continue":
                            keep_asking = False  # Exit the loop to continue improving
                        else:
                            print("⚠️ Invalid choice, please try again.")
                else:

                    # Export version immediately if auto mode and export_dir is set
                    if self.export_dir:
                        self._export_single_version(version, self.export_dir)
                    # Check if targets are achieved using the judge's decision
                    if version.judgement.meets_requirements:
                        if verbose:
                            print(
                                f"🎉 BOTH TARGETS ACHIEVED! Article reached world-class status with optimal length!"
                            )

                        self.generation_log.append(
                            f"Iteration {self.iteration}: Both targets achieved (Score: {version.judgement.percentage:.1f}%, Words: {version.judgement.word_count})"
                        )

                        break  # Exit loop if both targets are met

                    else:
                        if verbose:
                            f"⚠️ Iteration {self.iteration}: Targets not yet achieved: (Score: {version.judgement.percentage:.1f}%, Words: {version.judgement.word_count})"

                if finish_requested:
                    break

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

            # Auto-export if export_dir is specified and we have versions to export
            if self.export_dir and self.versions:
                if verbose:
                    print(
                        f"💾 Exporting versions summary to '{self.export_dir}' directory..."
                    )
                self._create_summary_md(self.export_dir)

        except KeyboardInterrupt:
            print("\n❌ Generation interrupted by user. Gracefully finish if possible")
        except Exception as e:
            print(f"❌ Error during generation: {e}. Gracefully finish if possible")
            if verbose:
                traceback.print_exc()

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
            "iterations_used": self.iteration,
            "versions": self.versions,
            "generation_log": self.generation_log,
            "word_count": final_word_count,
            "improvement_summary": self._generate_improvement_summary(),
        }

        return final_result

    def _generate_initial_article(
        self, draft_or_outline: str, context: str, verbose: bool
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

        context = context or self._perform_rag_search(draft_or_outline, verbose)

        if verbose and context:
            print(f"📚 Using context: {len(context)} characters")

        # Prepare generation inputs
        scoring_criteria = self.criteria_extractor.get_criteria_for_generation()

        try:
            # Validate context window before generation
            content_parts = {
                "draft": draft_or_outline,
                "context": context,
                "criteria": scoring_criteria,
            }

            try:
                self.context_manager.validate_content(content_parts)
            except ContextWindowError as e:
                if verbose:
                    print(f"⚠️ Context window validation failed: {e}")
                # Intelligently reduce context size instead of making it empty
                context = self.context_manager.reduce_context_size(
                    context, content_parts, verbose
                )
                content_parts["context"] = context
                # Validate again to ensure it now fits
                self.context_manager.validate_content(content_parts)

            # Generate initial article with comprehensive RAG context
            with dspy.context(lm=self.models["generator"].dspy_lm):
                result = self.generator(
                    original_draft=draft_or_outline,
                    context=context,
                    scoring_criteria=scoring_criteria,
                )

            return result.generated_article, context

        except Exception as e:
            if verbose:
                print(f"⚠️ Initial generation failed, using draft as fallback: {e}")

            # Fallback to original draft if generation fails
            return draft_or_outline, context or ""

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

        try:
            # Validate context window before improvement
            content_parts = {
                "current_article": current_article,
                "original_draft": self._get_original_draft(),
                "context": context,
                "feedback": judgement.improvement_prompt,
            }

            try:
                self.context_manager.validate_content(content_parts)
            except ContextWindowError as e:
                if verbose:
                    print(f"⚠️ Context window validation failed for improvement: {e}")
                # Intelligently reduce context size instead of making it empty
                context = self.context_manager.reduce_context_size(
                    context, content_parts, verbose
                )
                content_parts["context"] = context
                # Validate again to ensure it now fits
                self.context_manager.validate_content(content_parts)

            # Generate improved article using judge's improvement prompt
            with dspy.context(lm=self.models["generator"].dspy_lm):
                result = self.improver(
                    current_article=current_article,
                    original_draft=self._get_original_draft(),
                    context=context,
                    score_feedback=judgement.improvement_prompt,
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
        self, article_content: str, version_number: int, word_count: int
    ):
        """Print the article version content before sending it to be judged."""
        print(f"\n📄 ARTICLE VERSION {version_number} - SENDING TO JUDGE\n")
        print(f"\n📄 ARTICLE LENGTH: {word_count} words")
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

        print("=" * 60)

    def _get_user_decision(self, version: "ArticleVersion") -> str:
        """Ask user whether to continue improving or finish using contextual dashboard."""
        judgement = version.judgement

        # Generate progress dashboard
        dashboard = self.dashboard.generate_progress_dashboard(
            current_score=judgement.percentage,
            target_score=self.target_score_percentage,
            word_count=judgement.word_count,
            target_range=(
                self.word_count_manager.target_min,
                self.word_count_manager.target_max,
            ),
            overall_feedback=judgement.overall_feedback,
        )
        print(dashboard)

        prompt = self.interaction_manager.get_contextual_decision_prompt(
            current_score=judgement.percentage,
            improvement_prompt=judgement.improvement_prompt,
        )
        print(prompt)

        while True:
            try:
                choice = input("Enter your choice (1, 2, 3, or 4): ").strip().lower()
                if choice in ["1", "proceed", "p"]:
                    return "continue"
                elif choice in ["2", "add", "a", "instructions", "i"]:
                    return "instructions"
                elif choice in ["3", "export", "e"]:
                    return "export"
                elif choice in ["4", "finish", "f"]:
                    return "finish"
                else:
                    print("Please enter '1', '2', '3', or '4'")
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

    def _export_single_version(self, version: "ArticleVersion", directory_name: str):
        """Export a single article version to the specified directory.

        Args:
            version: The ArticleVersion to export
            directory_name: Directory name to export to
        """
        # Ensure directory exists
        # os.makedirs(directory_name, exist_ok=True)

        # Use version number for unique filename
        filename = f"version-{version.version}.md"
        filepath = os.path.join(directory_name, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                # Add version metadata header
                f.write(f"# Article Version {version.version}\n\n")
                f.write(f"**Generated:** {version.timestamp}\n")
                if version.judgement:
                    f.write(
                        f"**Score:** {version.judgement.percentage:.1f}% ({version.judgement.total_score}/{version.judgement.max_score})\n"
                    )
                    f.write(f"**Word Count:** {version.judgement.word_count}\n")
                    f.write(
                        f"**Performance Tier:** {version.judgement.performance_tier}\n"
                    )
                    if version.judgement.overall_feedback:
                        f.write(f"**Feedback:** {version.judgement.overall_feedback}\n")
                f.write("\n---\n\n")
                # Write the article content
                f.write(version.content)

            print(f"✅ Exported version {version.version} to {filename}")

        except Exception as e:
            print(f"❌ Failed to export version {version.version}: {e}")

    def _resolve_directory_name(self, base_name: str) -> str:
        """Resolve directory name with automatic numbering if conflicts exist.

        Args:
            base_name: The base directory name to use

        Returns:
            The resolved directory name (with numbering if needed)
        """
        if not os.path.exists(base_name):
            # Create the directory
            os.makedirs(base_name, exist_ok=False)
            return base_name

        counter = 1
        while True:
            candidate = f"{base_name}-{counter}"
            if not os.path.exists(candidate):
                os.makedirs(base_name, exist_ok=False)
                return candidate
            counter += 1

    def _export_version_to_directory(self, directory_name: Optional[str] = None):
        """Export all article versions to a user-specified directory.

        Args:
            directory_name: Optional directory name. If None, prompts user interactively.
        """
        print("\n💾 EXPORT ARTICLE VERSIONS")
        print("-" * 40)

        if not self.versions:
            print("❌ No versions available to export")
            return

        # Get directory name - either from parameter or user input
        if not directory_name:
            # Interactive mode - get directory name from user
            while True:
                try:
                    dir_name = input("Enter directory name for export: ").strip()
                    if not dir_name:
                        print("❌ Directory name cannot be empty")
                        continue

                    # Use automatic numbering for user input as well
                    directory_name = self._resolve_directory_name(dir_name)
                    if directory_name != dir_name:
                        print(
                            f"📁 Directory '{dir_name}' exists, using '{directory_name}' instead"
                        )
                    break

                except KeyboardInterrupt:
                    print("\n❌ Export cancelled")
                    return
                except Exception as e:
                    print(f"❌ Error with directory name: {e}")
                    return

        self.export_dir = directory_name

        # Export latest version
        version = self.versions[-1]
        self._export_single_version(version, self.export_dir)

        print(
            f"\n🎉 Successfully exported version {version.version} to '{directory_name}' directory"
        )
        print("📂 Returning to main menu...")

        return

        exported_count = 0
        for version in self.versions:
            filename = f"version-{version.version}.md"
            filepath = os.path.join(final_dir_name, filename)

            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    # Add version metadata header
                    f.write(f"# Article Version {version.version}\n\n")
                    f.write(f"**Generated:** {version.timestamp}\n")
                    if version.judgement:
                        f.write(
                            f"**Score:** {version.judgement.percentage:.1f}% ({version.judgement.total_score}/{version.judgement.max_score})\n"
                        )
                        f.write(f"**Word Count:** {version.judgement.word_count}\n")
                        f.write(
                            f"**Performance Tier:** {version.judgement.performance_tier}\n"
                        )
                        if version.judgement.overall_feedback:
                            f.write(
                                f"**Feedback:** {version.judgement.overall_feedback}\n"
                            )
                    f.write("\n---\n\n")
                    # Write the article content
                    f.write(version.content)

                exported_count += 1
                print(f"✅ Exported {filename}")

            except Exception as e:
                print(f"❌ Failed to export {filename}: {e}")

        # Create summary.md file for version comparison
        self._create_summary_md(final_dir_name)

        print(
            f"\n🎉 Successfully exported {exported_count} versions to '{final_dir_name}' directory"
        )
        print("📂 Returning to main menu...")

    def _create_summary_md(self, dir_name: str):
        """Create a summary.md file with version comparison table."""
        summary_path = os.path.join(dir_name, "summary.md")

        try:
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write("# Article Version Comparison Summary\n\n")

                # Generation metadata
                f.write("## Generation Overview\n\n")
                f.write(f"- **Target Score:** ≥{self.target_score_percentage}%\n")
                f.write(f"- **Max Iterations:** {self.max_iterations}\n")
                f.write(
                    f"- **Word Count Range:** {self.word_count_manager.target_min}-{self.word_count_manager.target_max}\n"
                )
                f.write(f"- **Total Versions:** {len(self.versions)}\n")
                f.write(
                    f"- **Final Score:** {self.versions[-1].judgement.percentage:.1f}%\n"
                )
                f.write(
                    f"- **Final Word Count:** {self.versions[-1].judgement.word_count}\n\n"
                )

                # Version comparison table
                f.write("## Version Comparison Table\n\n")
                f.write(
                    "| Version | Score | Percentage | Word Count | Performance Tier | Meets Requirements |\n"
                )
                f.write(
                    "|---------|-------|------------|------------|------------------|-------------------|\n"
                )

                for version in self.versions:
                    judgement = version.judgement
                    if judgement:
                        meets_req = (
                            "✅ Yes" if judgement.meets_requirements else "❌ No"
                        )
                        f.write(
                            f"| {version.version} | {judgement.total_score}/{judgement.max_score} | {judgement.percentage:.1f}% | {judgement.word_count} | {judgement.performance_tier} | {meets_req} |\n"
                        )
                    else:
                        f.write(
                            f"| {version.version} | N/A | N/A | N/A | N/A | N/A |\n"
                        )

                f.write("\n")

                # Score progression chart
                f.write("## Score Progression\n\n")
                f.write("```\n")
                max_score_width = 50
                for version in self.versions:
                    judgement = version.judgement
                    if judgement:
                        score_bar = "█" * int(
                            (judgement.percentage / 100) * max_score_width
                        )
                        f.write(
                            f"Version {version.version}: {score_bar} ({judgement.percentage:.1f}%)\n"
                        )
                f.write("```\n\n")

                # Detailed version breakdown
                f.write("## Detailed Version Analysis\n\n")
                for version in self.versions:
                    judgement = version.judgement
                    if judgement:
                        f.write(f"### Version {version.version}\n\n")
                        f.write(
                            f"- **Score:** {judgement.total_score}/{judgement.max_score} ({judgement.percentage:.1f}%)\n"
                        )
                        f.write(f"- **Word Count:** {judgement.word_count}\n")
                        f.write(
                            f"- **Performance Tier:** {judgement.performance_tier}\n"
                        )
                        f.write(
                            f"- **Meets Requirements:** {'✅ Yes' if judgement.meets_requirements else '❌ No'}\n"
                        )

                        f.write(
                            f"- **Article:** {version.content[:200]}{'...' if len(version.content) > 200 else ''}\n"
                        )

                        if judgement.overall_feedback:
                            f.write(
                                f"- **Overall Feedback:** {judgement.overall_feedback}\n"
                            )

                        if judgement.improvement_prompt and version.version < len(
                            self.versions
                        ):
                            f.write(
                                f"- **Improvement Prompt:** {judgement.improvement_prompt[:200]}{'...' if len(judgement.improvement_prompt) > 200 else ''}\n"
                            )

                        f.write(f"- **Generated:** {version.timestamp}\n\n")

                # Improvement summary
                if len(self.versions) > 1:
                    improvement_summary = self._generate_improvement_summary()
                    f.write("## Improvement Summary\n\n")
                    f.write(
                        f"- **Score Improvement:** +{improvement_summary['score_improvement']:.1f}%\n"
                    )
                    f.write(
                        f"- **Word Count Change:** {improvement_summary['word_count_change']:+d} words\n"
                    )
                    f.write(
                        f"- **Versions Created:** {improvement_summary['versions_created']}\n"
                    )
                    f.write(
                        f"- **Target Achieved:** {'✅ Yes' if improvement_summary['target_achieved'] else '❌ No'}\n\n"
                    )

                # Generation log
                f.write("## Generation Log\n\n")
                for log_entry in self.generation_log:
                    f.write(f"- {log_entry}\n")

                f.write(
                    "\n---\n\n*Generated on: "
                    + time.strftime("%Y-%m-%d %H:%M:%S")
                    + "*\n"
                )

            print("✅ Created summary.md with version comparison")

        except Exception as e:
            print(f"❌ Failed to create summary.md: {e}")

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
