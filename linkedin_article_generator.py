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
import logging

logging.basicConfig(level=logging.WARNING)


from models import ArticleVersion, JudgementModel
from li_article_judge import ComprehensiveLinkedInArticleJudge, CriteriaExtractor
from word_count_manager import WordCountManager
from dspy_factory import DspyModelConfig
from context_window_manager import ContextWindowManager, ContextWindowError
from rag_fast import retrieve_and_pack
from progress_dashboard import ProgressDashboard, UserInteractionManager
from output_manager import OutputManager
from humanizer import HumanizerModule


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

    ⚠️ CRITICAL LENGTH REQUIREMENT ⚠️
    - You MUST generate an article within the target_word_count range
    - Current article has current_word_count words
    - If current_word_count < target_word_count_min: ADD content to reach minimum
    - If current_word_count > target_word_count_max: CONDENSE to stay within maximum
    - This is NOT optional - length compliance is mandatory for acceptance

    WORD LENGTH STRATEGY:
    - When expanding: Focus on the high-priority suggestions in score_feedback to add quality content
    - When condensing: Preserve core arguments and remove redundancy
    - Balance quality improvements with length requirements

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
    - Apply improvements from score_feedback while meeting length requirements
    - Maintain professional LinkedIn tone and structure
    - Objective and third-person, with a more structured, business/technical tone
    - Preserve all key points from the original draft"""

    current_article = dspy.InputField(desc="Current version of the article")
    current_word_count = dspy.InputField(desc="Current article word count (integer)")
    target_word_count_min = dspy.InputField(desc="Minimum target word count (integer)")
    target_word_count_max = dspy.InputField(desc="Maximum target word count (integer)")
    original_draft = dspy.InputField(
        desc="Original draft for reference to maintain key points"
    )
    context = dspy.InputField(
        desc="String containing relevant content with inline markdown citations already formatted. Citations appear as [specific claim or data point](source_url) within the text.",
        default="",
    )
    score_feedback = dspy.InputField(
        desc="Detailed scoring feedback and improvement suggestions (length requirements already specified in dedicated fields above)"
    )

    improved_article = dspy.OutputField(
        desc="The improved article meeting ALL requirements above, especially the word count range."
    )


class LinkedInArticleGenerator(dspy.Module):
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
        writer_id: int,
        target_score_percentage: float,
        max_iterations: int,
        word_count_min: int,
        word_count_max: int,
        models: Dict[str, DspyModelConfig],
        verbose: bool,
        recreate_ctx: bool = False,
        auto: bool = False,
        export_dir: Optional[str] = None,
        output_manager: Optional["OutputManager"] = None,
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

        super().__init__()

        self.writer_id = writer_id
        self.version_id = 1  # Start with version 1 for the initial draft
        self.target_score_percentage = target_score_percentage
        self.max_iterations = max_iterations

        # Initialize OutputManager for beautiful verbose output
        self.output_manager = output_manager or OutputManager(
            writer_id, version_id=1, verbose=True
        )

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
        self.versions: List[ArticleVersion] = []
        self.generation_log: List[str] = []
        self.original_draft: Optional[str] = None
        self.recreate_ctx = recreate_ctx
        self.auto = auto

        if export_dir:
            # Use command-line specified directory with automatic numbering
            export_dir = self._resolve_directory_name(export_dir)
        self.export_dir = export_dir

        self.verbose = verbose

    def _perform_rag_search(
        self, draft_text: str, version_id: Optional[int] = None
    ) -> str:
        """
        Perform comprehensive RAG search and return context with inline citations.

        Args:
            draft_text: The draft article text to extract search queries from
            version_id: Optional version identifier for parallel execution

        Returns:
            Context with inline citations
        """
        try:
            ctx, urls = asyncio.run(
                retrieve_and_pack(
                    draft_text,
                    models=self.models,
                    context_manager=self.context_manager,
                    output_manager=self.output_manager,
                )
            )

            if ctx:
                return ctx
            else:
                return ""

        except Exception as e:
            logging.error(f"⚠️ RAG search failed: {e}")
            return ""

    def generate_article(self, initial_draft: str) -> Dict[str, Any]:
        """
        Generate a world-class LinkedIn article from a draft or outline.

        Args:
            initial_draft: Initial draft article or outline

        Returns:
            Dict containing final article, score, and generation metadata
        """
        self.output_manager.print_version_start()
        return self.generate_article_with_context(initial_draft, "")

    def generate_article_with_context(
        self,
        initial_draft: str,
        context: str = "",
    ) -> Dict[str, Any]:
        """
        Generate a world-class LinkedIn article from a draft or outline with web context.

        Args:
            initial_draft: Initial draft article or outline
            context: String containing relevant content with inline citations

        Returns:
            Dict containing final article, score, and generation metadata
        """

        # Clear previous generation data
        self.versions.clear()
        self.generation_log.clear()
        self.original_draft = initial_draft
        self.search_context = context or ""

        initial_article, initial_context = self._generate_initial_article(
            initial_draft, context
        )

        # Store draft version with a pending judgement
        initial_draft_judgement = JudgementModel(
            total_score=0,
            max_score=100,
            percentage=0.0,
            performance_tier="User provided draft",
            word_count=self.word_count_manager.count_words(initial_draft),
            meets_requirements=False,
            improvement_prompt="There is no improvement guidance since this is the user-provided draft, that will not be judged.",
            overall_feedback=None,  # Optional field for comprehensive feedback
            fact_check_result=None,  # Optional field for fact-checking results
        )

        # Create a temporary version for judging
        initial_draft_version = ArticleVersion(
            writer_id=self.writer_id,
            version_id=0,  # Version 0 for the initial draft
            content=initial_draft,
            context=initial_context,
            recreate_ctx=self.recreate_ctx,
            judgement=initial_draft_judgement,
        )

        self.versions.append(initial_draft_version)

        # Start iterative improvement process with the generated article
        final_result = self._iterative_improvement_process(
            initial_article, initial_context
        )

        self.output_manager.print_final_summary(final_result, self)

        return final_result

    def _iterative_improvement_process(
        self, initial_article: str, initial_context: str
    ) -> Dict[str, Any]:
        """Run the iterative improvement process with user interaction and combined quality and length validation."""
        current_article = initial_article
        current_context = initial_context
        user_instructions = ""  # Track user-provided instructions
        finish_requested = False  # Track if user requested to finish early

        try:
            # Ensure at least one iteration runs to get a judgement
            while self.version_id <= max(1, self.max_iterations):

                self.output_manager.print_iteration_start(
                    self.version_id, max(1, self.max_iterations)
                )

                word_count = self.word_count_manager.count_words(current_article)

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
                    fact_check_result=None,  # Optional field for fact-checking results
                )

                # Create a temporary version for judging
                temp_version = ArticleVersion(
                    writer_id=self.writer_id,
                    version_id=self.version_id,
                    content=current_article,
                    context=current_context,
                    recreate_ctx=self.recreate_ctx,
                    judgement=pending_judgement,  # Pending placeholder
                )

                # Judge with the temporary version included
                self.output_manager.print_version_judging()
                prediction = self.judge(self.versions + [temp_version])

                # Judged version to append
                version = prediction.output  # This is the real judgement
                judgement = version.judgement
                self.output_manager.print_version_judgement(judgement)
                self.versions.append(version)

                self.generation_log.append(
                    f"Version {version.version_id}: Improved article ({version.judgement.word_count} words, improvement {version.judgement.improvement_prompt})"
                )

                if self.auto == False:

                    keep_asking = True
                    while keep_asking:

                        user_decision = self._get_user_decision(version)

                        if user_decision == "finish":
                            keep_asking = False  # Default to not asking again
                            # break out of loop while self.version_id < max(1, self.max_iterations): to finish
                            finish_requested = True

                        elif user_decision == "instructions":
                            keep_asking = False
                            user_instructions = self._get_user_instructions()
                            # Prepend user instructions to judge's improvement prompt if provided
                            if user_instructions:
                                judgement.improvement_prompt = f"""THESE ARE NEW INSTRUCTIONS:
    <NEW>
    PRIORITIZE THE FOLLOWING USER INSTRUCTIONS FOR THE NEXT IMPROVEMENT ITERATION:
    {user_instructions}\n\n
    FOLLOWING ARE THE GENERATED IMPROVEMENT GUIDANCE BELOW:
    {judgement.improvement_prompt}
    <NEW/>"""
                        elif user_decision == "export":
                            self._export_version_to_directory(self.export_dir)
                            continue  # Return to menu after export
                        elif user_decision == "fact_check":
                            # Export non-fact-checked version first
                            self._export_version_to_directory(self.export_dir)
                            # Then perform fact-checking
                            self._perform_fact_check_on_version(version)
                            continue  # Return to menu after fact-checking
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

                        # Automatically perform fact-checking when targets are met
                        self.output_manager.print_version_message(
                            "Quality and length targets achieved — performing automatic fact-checking...",
                            emoji="🎯",
                        )
                        self._perform_fact_check_on_version(version)

                        self.generation_log.append(
                            f"Version {self.version_id}: Both targets achieved (Score: {version.judgement.percentage:.1f}%, Words: {version.judgement.word_count}) - Fact-checked"
                        )

                        break  # Exit loop if both targets are met

                if finish_requested:
                    break

                # Start next generation version
                self.version_id += 1
                self.output_manager.set_version_id(self.version_id)
                improved_article, used_context = (
                    self._generate_improved_version_with_judgement(
                        current_article, judgement
                    )
                )

                current_article = improved_article
                current_context = used_context

            # Auto-export if export_dir is specified and we have versions to export
            if self.export_dir and self.versions:
                self._create_summary_md(self.export_dir)

        except KeyboardInterrupt:
            logging.info(
                "\n❌ Generation interrupted by user. Gracefully finish if possible"
            )
        except Exception as e:
            logging.error(
                f"❌ Error during generation: {e}. Gracefully finish if possible"
            )
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
            "writer_id": self.writer_id,
            "final_article": current_article,
            "final_score": final_judgement,
            "target_achieved": both_targets_achieved,
            "quality_achieved": final_quality_achieved,
            "length_achieved": final_length_achieved,
            "iterations_used": self.version_id,
            "versions": self.versions,
            "generation_log": self.generation_log,
            "word_count": final_word_count,
            "improvement_summary": self._generate_improvement_summary(),
        }

        # Humanization — final trusted post-processing step
        self.output_manager.print_humanizing_start()
        original_article = final_result["final_article"]
        try:
            humanizer_cfg = self.models.get("humanizer") or self.models["generator"]
            with dspy.context(lm=humanizer_cfg.dspy_lm):
                humanizer = HumanizerModule(output_manager=self.output_manager)
                humanizer_result = humanizer(article=original_article)
            humanized_article = humanizer_result["humanized_article"]
            detection_scores = humanizer_result.get("detection")
        except Exception as e:
            logging.error(f"Humanization failed: {e}")
            humanized_article = original_article
            detection_scores = None

        final_result["original_article"] = original_article
        final_result["humanized_article"] = humanized_article
        final_result["detection_scores"] = detection_scores
        self.output_manager.print_humanizing_complete()

        return final_result

    def _generate_initial_article(
        self,
        draft_or_outline: str,
        context: str,
        version_id: Optional[int] = None,
    ) -> Tuple[str, str]:
        """Generate initial markdown article from draft/outline using ArticleGenerationSignature.

        Returns:
            Tuple of (generated_article, context_used)
        """

        if not context:
            # Perform RAG search if no context provided
            self.output_manager.print_version_rag_search()
            context = self._perform_rag_search(draft_or_outline, version_id)

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
                logging.error(f"⚠️ Context window validation failed: {e}")
                # Intelligently reduce context size instead of making it empty
                context = self.context_manager.reduce_context_size(
                    context,
                    content_parts,
                )
                content_parts["context"] = context
                # Validate again to ensure it now fits
                self.context_manager.validate_content(content_parts)

            self.output_manager.print_version_ctx_details(context)

            # Generate initial article with comprehensive RAG context
            self.output_manager.print_version_generation()
            with dspy.context(lm=self.models["generator"].dspy_lm):
                result = self.generator(
                    original_draft=draft_or_outline,
                    context=context,
                    scoring_criteria=scoring_criteria,
                )

            return result.generated_article, context

        except Exception as e:
            logging.error(f"⚠️ Initial generation failed, using draft as fallback: {e}")

            # Fallback to original draft if generation fails
            return draft_or_outline, context or ""

    def _generate_improved_version_with_judgement(
        self,
        current_article: str,
        judgement: JudgementModel,
    ) -> Tuple[str, str]:
        """Generate an improved version using the judge's improvement prompt.

        Returns:
            Tuple of (improved_article, context_used)
        """

        # Determine context based on recreate_ctx flag
        self.output_manager.print_version_context_reuse(self.recreate_ctx)

        if self.recreate_ctx:
            # Perform fresh RAG search for improvement context
            context = self._perform_rag_search(current_article)
        else:
            # Reuse context from the first version
            if self.versions and len(self.versions) > 0:
                context = self.versions[0].context
            else:
                # Fallback if no versions exist yet
                self.output_manager.print_version_message(
                    "No initial context available, performing fresh search...", "⚠️"
                )
                context = self._perform_rag_search(current_article)

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
                logging.error(
                    f"⚠️ Context window validation failed for improvement: {e}"
                )
                # Intelligently reduce context size instead of making it empty
                context = self.context_manager.reduce_context_size(
                    context, content_parts
                )
                content_parts["context"] = context
                # Validate again to ensure it now fits
                self.context_manager.validate_content(content_parts)

            self.output_manager.print_version_generation()

            # Generate improved article using judge's improvement prompt
            with dspy.context(lm=self.models["generator"].dspy_lm):
                result = self.improver(
                    current_article=current_article,
                    current_word_count=judgement.word_count,
                    target_word_count_min=self.word_count_manager.target_min,
                    target_word_count_max=self.word_count_manager.target_max,
                    original_draft=self._get_original_draft(),
                    context=context,
                    score_feedback=judgement.improvement_prompt,
                )

            return result.improved_article, context

        except Exception as e:
            logging.error(
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

    def _get_user_decision(self, version: "ArticleVersion") -> str:
        """Ask user whether to continue improving or finish using contextual dashboard."""
        judgement = version.judgement

        # Display article status
        print(
            f"\nYour article score is {judgement.percentage:.1f}% with length {judgement.word_count} words."
        )
        print("")

        # Display menu options in consistent format
        print("Choose your next action:")
        print("  1. ✅ Proceed with these improvements")
        print("  2. ✏️  Add specific instructions for this iteration")
        print("  3. 💾 Export this version to directory")
        print("  4. 🔍 Fact-check current version")
        print("  5. 🏁 Finish with current version")

        while True:
            try:
                choice = (
                    input("\nEnter your choice (1, 2, 3, 4, or 5): ").strip().lower()
                )
                if choice in ["1", "proceed", "p"]:
                    return "continue"
                elif choice in ["2", "add", "a", "instructions", "i"]:
                    return "instructions"
                elif choice in ["3", "export", "e"]:
                    return "export"
                elif choice in ["4", "fact", "fc", "fact-check"]:
                    return "fact_check"
                elif choice in ["5", "finish", "f"]:
                    return "finish"
                else:
                    print("Please enter '1', '2', '3', '4', or '5'")
            except KeyboardInterrupt:
                print("\nOperation cancelled by user.")
                return "finish"

    def _perform_fact_check_on_version(self, version: "ArticleVersion"):
        """
        Perform fact-checking on a version and export results.

        Args:
            version: The ArticleVersion to fact-check
        """
        self.output_manager.print_fact_checking_start()

        # Perform fact-checking
        fact_checked_article, fact_check_result, changes_made = (
            self.judge.perform_fact_check(version)
        )

        self.output_manager.print_fact_checking_results(fact_check_result)
        if fact_check_result.fact_check_passed:
            self.output_manager.print_fact_checking_passed()
        else:
            self.output_manager.print_fact_checking_failed(
                fact_check_result.summary_feedback or ""
            )

        # Export fact-checked version if export_dir is set
        if self.export_dir:
            # Export fact-checked article
            fc_filename = f"version-{version.version_id}-fc.md"
            fc_filepath = os.path.join(self.export_dir, fc_filename)

            try:
                with open(fc_filepath, "w", encoding="utf-8") as f:
                    # Add metadata header
                    f.write(
                        f"# Article Version {version.version_id} - Fact-Checked\n\n"
                    )
                    f.write(f"**Original Version:** {version.version_id}\n")
                    f.write(
                        f"**Fact-Check Status:** {'Passed' if fact_check_result.fact_check_passed else 'Changes Applied'}\n"
                    )
                    f.write(f"**Changes Made:** {len(changes_made)}\n")
                    f.write(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("\n---\n\n")
                    # Write the fact-checked article
                    f.write(fact_checked_article)

                print(f"\n✅ Exported fact-checked article: {fc_filepath}")
            except Exception as e:
                print(f"❌ Failed to export fact-checked article: {e}")

            # Export changes JSON
            changes_filename = f"version-{version.version_id}-fc-changes.json"
            changes_filepath = os.path.join(self.export_dir, changes_filename)

            try:
                changes_data = {
                    "version": version.version_id,
                    "fact_check_passed": fact_check_result.fact_check_passed,
                    "summary": fact_check_result.summary_feedback,
                    "changes": [
                        {
                            "original": change.original,
                            "updated": change.updated,
                            "reason": change.reason,
                            "citation": change.citation,
                        }
                        for change in changes_made
                    ],
                }

                with open(changes_filepath, "w", encoding="utf-8") as f:
                    json.dump(changes_data, f, indent=2, ensure_ascii=False)

                print(f"✅ Exported fact-check changes: {changes_filepath}")
            except Exception as e:
                print(f"❌ Failed to export fact-check changes: {e}")
        else:
            print("\n⚠️ No export directory set - fact-checked version not saved")
            print("   Use --export_dir to automatically save fact-checked versions")

        print("\n" + "=" * 60)

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
        """Print a comprehensive final summary using OutputManager."""
        self.output_manager.print_final_summary(final_result, self)

    def get_version_history(self) -> List[Dict[str, Any]]:
        """Get a summary of all article versions."""
        history = []

        for version in self.versions:
            version_info = {
                "version": version.version_id,
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
        filename = f"version-{version.version_id}.md"
        filepath = os.path.join(directory_name, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                # Add version metadata header
                f.write(f"# Article Version {version.version_id}\n\n")
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

            self.output_manager.print_version_exporting(filepath)

        except Exception as e:
            print(f"❌ Failed to export version {version.version_id}: {e}")

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
                os.makedirs(candidate, exist_ok=False)
                return candidate
            counter += 1

    def _export_version_to_directory(self, directory_name: Optional[str] = None):
        """Export all article versions to a user-specified directory.

        Args:
            directory_name: Optional directory name. If None, prompts user interactively.
        """
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

        return

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
                    "| Version | Score | Percentage | Word Count | Performance Tier | Meets Requirements | Fact-Checked |\n"
                )
                f.write(
                    "|---------|-------|------------|------------|------------------|-------------------|-------------|\n"
                )

                for version in self.versions:
                    judgement = version.judgement
                    if judgement:
                        meets_req = (
                            "✅ Yes" if judgement.meets_requirements else "❌ No"
                        )
                        # Check if fact-checked version exists
                        fc_filename = f"version-{version.version_id}-fc.md"
                        fc_path = os.path.join(dir_name, fc_filename)
                        fact_checked = "✅ Yes" if os.path.exists(fc_path) else "❌ No"

                        f.write(
                            f"| {version.version_id} | {judgement.total_score}/{judgement.max_score} | {judgement.percentage:.1f}% | {judgement.word_count} | {judgement.performance_tier} | {meets_req} | {fact_checked} |\n"
                        )
                    else:
                        f.write(
                            f"| {version.version_id} | N/A | N/A | N/A | N/A | N/A | N/A |\n"
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
                            f"Version {version.version_id}: {score_bar} ({judgement.percentage:.1f}%)\n"
                        )
                f.write("```\n\n")

                # Detailed version breakdown
                f.write("## Detailed Version Analysis\n\n")
                for version in self.versions:
                    judgement = version.judgement
                    if judgement:
                        f.write(f"### Version {version.version_id}\n\n")
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

                        if judgement.improvement_prompt and version.version_id < len(
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
