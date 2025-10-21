#!/usr/bin/env python3
"""
Output Manager - Centralized Output Handling

This module provides a unified OutputManager class that consolidates all output
statements from across the LinkedIn Article Generator project. It ensures
consistent version prefixing and formatting for both single and parallel modes.
"""

from typing import Dict, Any, List, Optional
import time
import re
import argparse
from li_article_judge import JudgementModel


class OutputManager:
    """
    Centralized manager for all output formatting and display.

    Handles both single version mode (always VERSION 1) and parallel version mode
    (VERSION 2, VERSION 3, etc.) with consistent formatting and version prefixing.
    """

    def __init__(self, writer_id: int, version_id: int, verbose: bool):
        """
        Initialize the OutputManager.

        Args:
            version_id: Version identifier (1 for single mode, 2+ for parallel mode)
            verbose: Whether to display verbose output
        """
        self.writer_id = writer_id
        self.version_id = version_id
        self.verbose = verbose

    def _format_version_message(self, message: str, emoji: str = "📝") -> str:
        """
        Format a message with consistent version prefix.

        Args:
            message: The message to format
            emoji: Emoji to use in the prefix

        Returns:
            Formatted message with version prefix
        """
        return f"[{emoji} WRITER-VERSION {self.writer_id}-{self.version_id}] {message}"

    def _print_if_verbose(self, message: str):
        """Print message only if verbose mode is enabled."""
        if self.verbose:
            print(message)

    # ============================================================================
    # GEOFF-ADDED METHODS
    # ============================================================================

    def set_version_id(self, version_id: int):
        """Set the version ID for this output manager."""
        self.version_id = version_id

    def print_version_ctx_details(self, ctx: str):
        """Print details of context being passed to article generation."""

        # ctx is a string of markdown formatted links of form [display text](url).
        # Use regex to extract the found urls into a list object.
        urls = re.findall(r"\[.*?\]\((https?://[^\s)]+)\)", ctx)
        num_urls = len(urls)
        # convert list to a set to remove duplicates so I can count unique urls
        unique_urls = set(urls)
        num_unique_urls = len(unique_urls)
        message = self._format_version_message(
            f"Passing ctx of {num_urls} citations from {num_unique_urls} urls to article generation",
            "📚",
        )
        print(message)

    def print_version_message(self, message: str, emoji: str = "📝"):
        """Print a custom versioned message."""
        formatted_message = self._format_version_message(message, emoji)
        print(formatted_message)

    def print_version_start(self):
        """Print version start message."""
        message = self._format_version_message("Starting generation process...", "🚀")
        print(message)

    def print_version_rag_search(self):
        """Print version RAG search start message."""
        message = self._format_version_message(
            "Searching web to create RAG context...", "🌐"
        )
        print(message)

    def print_version_generation(self):
        """Print version generation start message."""

        message = self._format_version_message(
            f"Generating this version of article...", "🔄"
        )
        print(message)

    def print_version_judging(self):
        """Print version judging start message."""
        message = self._format_version_message("Evaluating article quality...", "🎯")
        print(message)

    def print_version_judgement(self, judgement: JudgementModel):
        """Print version exporting to dir message."""
        message = self._format_version_message(
            f"Judging Status. Score: {judgement.total_score}/{judgement.max_score} ({judgement.percentage:.1f}%) Length: {judgement.word_count}\n\n{judgement.overall_feedback}",
            "🎯",
        )
        print(message)

    def print_version_exporting(self, directory: str):
        """Print version exporting to dir message."""
        message = self._format_version_message(f"\nSaved to {directory}\n", "🎯")
        print(message)

    def print_version_context_reuse(self, recreate_ctx: bool):
        """Print context reuse or fresh search status."""

        if recreate_ctx:
            message = self._format_version_message(
                "Performing fresh RAG search (recreate_ctx=True)", "🔄"
            )
        else:
            message = self._format_version_message(
                "Reusing initial context - maintaining consistency", "🔄"
            )

        print(message)

    def print_version_context_query(self, queries: List[str]):
        """Print context search queries."""

        message = self._format_version_message(
            f"RAG Search Queries: {', '.join(queries)}", "🌐"
        )
        print(message)

    # ============================================================================
    # VERSION-SPECIFIC METHODS (from main.py)
    # ============================================================================

    def print_version_complete(
        self, score: Optional[float] = None, success: bool = True
    ):
        """Print version completion message."""
        if success and score is not None:
            message = self._format_version_message(
                f"Completed with score: {score:.1f}%", "✅"
            )
        elif success:
            message = self._format_version_message("Completed successfully", "✅")
        else:
            message = self._format_version_message("Failed to generate", "❌")
        print(message)

    # ============================================================================
    # VERBOSE MANAGER METHODS (from linkedin_article_generator.py)
    # ============================================================================

    def print_section_header(
        self, title: str, emoji: str = "📋", style: str = "double"
    ):
        """Print a formatted section header with enhanced borders and styling."""
        if not self.verbose:
            return

        title_width = len(title) + len(emoji) + 2
        border_width = max(60, title_width + 4)

        if style == "double":
            border = "═" * border_width
            side = "║"
        elif style == "single":
            border = "─" * border_width
            side = "│"
        elif style == "rounded":
            border = "─" * border_width
            side = "│"
        else:
            border = "=" * border_width
            side = "|"

        print(f"\n{border}")
        print(f"{side} {emoji} {title.upper()} {side}")
        print(f"{border}")

    def print_generation_start(self, generator_instance):
        """Print beautiful generation start header with all key parameters."""
        if not self.verbose:
            return

        self.print_section_header("LinkedIn Article Generation Process", "🚀", "double")

        print("📊 CONFIGURATION PARAMETERS:")
        print("  ┌─────────────────────────────────────────────────────────────┐")
        print("  │" + " " * 61 + "│")
        print(
            f"  │  🎯 Target Score: ≥{generator_instance.target_score_percentage}%{' ' * (35 - len(str(generator_instance.target_score_percentage)))}│"
        )
        print(
            f"  │  🔄 Max Iterations: {generator_instance.max_iterations}{' ' * (37 - len(str(generator_instance.max_iterations)))}│"
        )
        print(
            f"  │  📏 Word Count Range: {generator_instance.word_count_manager.target_min}-{generator_instance.word_count_manager.target_max}{' ' * (28 - len(str(generator_instance.word_count_manager.target_min)) - len(str(generator_instance.word_count_manager.target_max)))}│"
        )
        print("  │" + " " * 61 + "│")
        print("  │  🤖 MODELS CONFIGURATION:" + " " * 35 + "│")
        print("  │" + " " * 61 + "│")
        print(
            f"  │  ✍️  Generator: {generator_instance.models['generator'].name[:35]}{' ' * (35 - min(35, len(generator_instance.models['generator'].name)))}│"
        )
        print(
            f"  │  🎯 Judge: {generator_instance.models['judge'].name[:35]}{' ' * (35 - min(35, len(generator_instance.models['judge'].name)))}│"
        )
        print(
            f"  │  🌐 RAG: {generator_instance.models['rag'].name[:35]}{' ' * (35 - min(35, len(generator_instance.models['rag'].name)))}│"
        )
        print("  │" + " " * 61 + "│")
        print(
            f"  │  🔄 Recreate Context: {generator_instance.recreate_ctx}{' ' * (35 - len(str(generator_instance.recreate_ctx)))}│"
        )
        print("  └─────────────────────────────────────────────────────────────┘")

    def print_rag_status(self, context_length: int, urls: Optional[List[str]] = None):
        """Print RAG search results and context information."""
        if not self.verbose:
            return

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

    def print_generation_phase(self, phase: str, details: str = ""):
        """Print generation phase status."""
        if not self.verbose:
            return

        print(f"\n📝 {phase.upper()}")
        if details:
            print(f"  {details}")

    def print_final_summary(self, final_result: Dict[str, Any], generator_instance):
        """Print comprehensive final summary with all metrics."""
        if not self.verbose:
            return

        self.print_section_header("Final Results", "🏆", "double")

        final_score = final_result["final_score"]
        improvement_summary = final_result["improvement_summary"]

        # Final metrics in a structured box
        print("📊 FINAL METRICS:")
        print(
            "  ┌─────────────────────────────────────────────────────────────────────┐"
        )
        print("  │" + " " * 69 + "│")

        # Score information
        score_display = f"🎯 Score: {final_score.total_score}/{final_score.max_score} ({final_score.percentage:.1f}%)"
        target_display = f"🎯 Target: ≥{generator_instance.target_score_percentage}%"
        score_line = f"{score_display} │ {target_display}"
        padding = 69 - len(score_line)
        print(f"  │  {score_line}{' ' * padding}│")

        # Achievement status
        quality_status = "✅ YES" if final_result["quality_achieved"] else "❌ NO"
        length_status = "✅ YES" if final_result["length_achieved"] else "❌ NO"
        overall_status = "✅ YES" if final_result["target_achieved"] else "❌ NO"

        status_display = f"🏆 Quality: {quality_status} │ Length: {length_status} │ Overall: {overall_status}"
        padding = 69 - len(status_display)
        print(f"  │  {status_display}{' ' * padding}│")

        # Iteration and word count
        iter_display = f"🔄 Iterations: {final_result['iterations_used']}/{generator_instance.max_iterations}"
        word_display = f"📝 Words: {final_result['word_count']}"
        iter_line = f"{iter_display} │ {word_display}"
        padding = 69 - len(iter_line)
        print(f"  │  {iter_line}{' ' * padding}│")

        print("  │" + " " * 69 + "│")
        print(
            "  └─────────────────────────────────────────────────────────────────────┘"
        )

        if len(generator_instance.versions) > 1:
            print("\n📈 IMPROVEMENT SUMMARY:")
            print(
                "  ┌─────────────────────────────────────────────────────────────────────┐"
            )
            print("  │" + " " * 69 + "│")

            score_imp = (
                f"📈 Score Change: {improvement_summary['score_improvement']:+.1f}%"
            )
            word_change = (
                f"📝 Word Change: {improvement_summary['word_count_change']:+d}"
            )
            versions = f"🔢 Versions: {improvement_summary['versions_created']}"

            padding = 69 - len(score_imp)
            print(f"  │  {score_imp}{' ' * padding}│")
            padding = 69 - len(word_change)
            print(f"  │  {word_change}{' ' * padding}│")
            padding = 69 - len(versions)
            print(f"  │  {versions}{' ' * padding}│")

            print("  │" + " " * 69 + "│")
            print(
                "  └─────────────────────────────────────────────────────────────────────┘"
            )

        print("\n📋 GENERATION LOG:")
        print(
            "  ┌─────────────────────────────────────────────────────────────────────┐"
        )
        for i, log_entry in enumerate(
            final_result["generation_log"][:8], 1
        ):  # Show first 8 entries
            log_display = f"{i}. {log_entry}"
            if len(log_display) > 65:
                log_display = log_display[:62] + "..."
            padding = 69 - len(log_display)
            print(f"  │  {log_display}{' ' * padding}│")
        if len(final_result["generation_log"]) > 8:
            remaining = len(final_result["generation_log"]) - 8
            remaining_display = f"... and {remaining} more entries"
            padding = 69 - len(remaining_display)
            print(f"  │  {remaining_display}{' ' * padding}│")
        print(
            "  └─────────────────────────────────────────────────────────────────────┘"
        )

        # Success/failure message
        if final_result["target_achieved"]:
            print("\n" + "═" * 70)
            print("🎉 SUCCESS! Article achieved world-class status!")
            print("═" * 70)
        else:
            print("\n" + "─" * 70)
            print(
                f"💡 Continue improving to reach the {generator_instance.target_score_percentage}% target."
            )
            print("─" * 70)

    def print_variable_dump(
        self, variables: Dict[str, Any], title: str = "Variable Dump"
    ):
        """Print debug dump of key variables."""
        if not self.verbose:
            return

        print(f"\n🔧 {title.upper()}")
        print("-" * 40)
        for key, value in variables.items():
            if isinstance(value, (int, float)):
                print(f"  • {key}: {value}")
            elif isinstance(value, str) and len(value) > 100:
                print(f"  • {key}: {value[:100]}... (truncated)")
            else:
                print(f"  • {key}: {value}")

    # ============================================================================
    # ARTICLE JUDGING AND EXPORT METHODS
    # ============================================================================

    def print_article_version_before_judging(
        self, article_content: str, version_number: int, word_count: int
    ):
        """Print the article version content before sending it to be judged."""
        if not self.verbose:
            return

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

    def print_judging_results_after_judging(self, version):
        """Print comprehensive judging results after evaluation."""
        if not self.verbose:
            return

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

    # ============================================================================
    # PARALLEL MODE COMPARISON AND SELECTION METHODS
    # ============================================================================

    def display_version_comparison(self, results: List[Dict[str, Any]]) -> None:
        """
        Display a comparison table of all generated versions.

        Args:
            results: List of generation results
        """
        print("\n" + "=" * 100)
        print("📊 VERSION COMPARISON")
        print("=" * 100)

        # Header
        print(
            f"{'Version':<10}{'Status':<15}{'Score':<10}{'Words':<10}{'Time':<10}{'Temp':<10}"
        )
        print("-" * 100)

        successful_results = [r for r in results if r["success"]]

        for result in results:
            version = result["version"]
            success = result["success"]

            if success:
                score = result["result"]["final_score"].percentage
                word_count = result["result"]["word_count"]
                gen_time = result["generation_time"]
                temp = result["temperature"]
                status = "✅ Success"
            else:
                score = word_count = gen_time = temp = "N/A"
                status = f"❌ Failed: {result['error'][:50]}..."

            print(
                f"{version:<10}{status:<15}{score:<10}{word_count:<10}{gen_time:<10}{temp:<10}"
            )

        print("=" * 100)

        if successful_results:
            print(f"\n🎯 {len(successful_results)} versions generated successfully")
            print(
                f"📈 Best score: {max(r['result']['final_score'].percentage for r in successful_results):.1f}%"
            )
            print(
                f"⏱️  Fastest generation: {min(r['generation_time'] for r in successful_results):.1f}s"
            )
        else:
            print("\n❌ All versions failed to generate")

    def print_export_success(self, version_number: int, filepath: str):
        """Print successful export message."""
        print(f"✅ Exported version {version_number} to {filepath}")

    def print_export_failure(self, version_number: int, error: str):
        """Print export failure message."""
        print(f"❌ Failed to export version {version_number}: {error}")

    def print_export_directory_created(self, directory_name: str):
        """Print directory creation message."""
        print(f"📁 Using directory: {directory_name}")

    def print_export_directory_conflict(self, original_name: str, resolved_name: str):
        """Print directory conflict resolution message."""
        print(f"📁 Directory '{original_name}' exists, using '{resolved_name}' instead")

    # ============================================================================
    # FACT-CHECKING OUTPUT METHODS
    # ============================================================================

    def print_fact_checking_start(self):
        """Print fact-checking start message."""
        message = self._format_version_message(
            "Starting fact-checking validation...", "🔍"
        )
        print(message)

    def print_fact_checking_results(self, fact_check_result):
        """Print comprehensive fact-checking results."""
        if not fact_check_result:
            return

        message = self._format_version_message("FACT-CHECKING RESULTS", "🔍")
        print(f"\n{message}")
        print("─" * 80)

        # Summary statistics
        print("📊 FACT-CHECKING SUMMARY:")
        print(f"  • Total Claims Found: {fact_check_result.total_claims_found}")
        print(f"  • Claims with Citations: {fact_check_result.claims_with_citations}")
        print(f"  • Valid Citations: {fact_check_result.valid_citations}")
        print(f"  • Invalid Citations: {fact_check_result.invalid_citations}")
        print(f"  • Uncited Claims: {fact_check_result.uncited_claims}")

        # Overall status
        status_emoji = "✅" if fact_check_result.fact_check_passed else "❌"
        status_text = "PASSED" if fact_check_result.fact_check_passed else "FAILED"
        print(f"\n{status_emoji} FACT-CHECK STATUS: {status_text}")

        # Summary feedback
        if fact_check_result.summary_feedback:
            print(f"\n💬 SUMMARY: {fact_check_result.summary_feedback}")

        # Detailed feedback if there are issues
        if fact_check_result.improvement_needed and fact_check_result.detailed_feedback:
            print(f"\n🔧 DETAILED FEEDBACK:")
            print("─" * 60)

            # Split detailed feedback into lines for better formatting
            feedback_lines = fact_check_result.detailed_feedback.split("\n")
            for line in feedback_lines:
                if line.strip():
                    print(f"  {line}")

        print("─" * 80)

    def print_citation_issues(self, invalid_citations: int, uncited_claims: int):
        """Print specific citation issues found."""
        if invalid_citations > 0 or uncited_claims > 0:
            message = self._format_version_message("CITATION ISSUES DETECTED", "⚠️")
            print(f"\n{message}")

            if invalid_citations > 0:
                print(f"  🚨 {invalid_citations} invalid citations need correction")

            if uncited_claims > 0:
                print(f"  📝 {uncited_claims} factual claims need citations")

    def print_fact_checking_passed(self):
        """Print fact-checking success message."""
        message = self._format_version_message("Fact-checking validation passed!", "✅")
        print(message)

    def print_fact_checking_failed(self, reason: str = ""):
        """Print fact-checking failure message."""
        base_message = "Fact-checking validation failed"
        full_message = f"{base_message}: {reason}" if reason else base_message
        message = self._format_version_message(full_message, "❌")
        print(message)

    # ============================================================================
    # SCORE REPORTING METHODS (from li_article_judge.py)
    # ============================================================================

    def print_score_report(self, score) -> None:
        """
        Print a formatted report of the article scoring results with version header.

        Args:
            score: The scoring model object (JudgementModel or ArticleScoreModel)
        """
        # Import here to avoid circular imports
        from li_article_judge import SCORING_CRITERIA

        version_header = self._format_version_message(
            "ARTICLE QUALITY SCORE REPORT", "📋"
        )

        print("\n" + "═" * 90)
        print(version_header)
        print("═" * 90)

        # Overall score in a prominent box
        print("🎯 OVERALL PERFORMANCE:")
        print(
            "  ┌─────────────────────────────────────────────────────────────────────────────┐"
        )
        print("  │" + " " * 77 + "│")

        score_display = (
            f"📊 Score: {score.total_score}/{score.max_score} ({score.percentage:.1f}%)"
        )
        padding = 77 - len(score_display)
        print(f"  │  {score_display}{' ' * padding}│")

        tier_display = f"🏆 Tier: {score.performance_tier}"
        padding = 77 - len(tier_display)
        print(f"  │  {tier_display}{' ' * padding}│")

        if hasattr(score, "word_count") and score.word_count is not None:
            word_display = f"📝 Words: {score.word_count}"
            padding = 77 - len(word_display)
            print(f"  │  {word_display}{' ' * padding}│")

        print("  │" + " " * 77 + "│")
        print(
            "  └─────────────────────────────────────────────────────────────────────────────┘"
        )

        # Check if this is the old ArticleScoreModel with category_scores
        if hasattr(score, "category_scores"):
            print("\n📊 DETAILED CATEGORY BREAKDOWN:")
            print("─" * 90)

            for category, results in score.category_scores.items():
                category_score = sum(r.score for r in results)
                # Calculate category max based on actual point values
                category_max = sum(
                    SCORING_CRITERIA[category][i].get("points", 5)
                    for i in range(len(results))
                )

                # Category header with score
                print(f"📁 {category}")
                print(
                    f"   Score: {category_score}/{category_max} ({category_score/category_max*100:.1f}%)"
                )
                print("   " + "─" * 60)

                for i, result in enumerate(results):
                    criterion_points = SCORING_CRITERIA[category][i].get("points", 5)
                    print(f"   • {result.criterion}")
                    print(f"     Rating: {result.score}/{criterion_points}")
                    print(f"     Analysis: {result.reasoning}")
                    if result.suggestions:
                        print(f"     💡 Suggestion: {result.suggestions}")
                    print()
        else:
            # For simplified JudgementModel, show basic category breakdown
            print("\n📊 CATEGORY SUMMARY:")
            print("─" * 90)

            total_possible = 180  # Known total from criteria
            for category_name, criteria in SCORING_CRITERIA.items():
                category_max = sum(c.get("points", 5) for c in criteria)
                # Estimate category score proportionally
                estimated_score = int(
                    (score.total_score / total_possible) * category_max
                )

                percentage = (
                    (estimated_score / category_max * 100) if category_max > 0 else 0
                )
                print(
                    f"📁 {category_name}: {estimated_score}/{category_max} ({percentage:.1f}%)"
                )

        # Display overall feedback if available
        if hasattr(score, "overall_feedback") and score.overall_feedback:
            print("\n💬 OVERALL FEEDBACK:")
            print("─" * 90)

            # Split feedback into lines and display in a box
            feedback_lines = score.overall_feedback.split("\n")
            print(
                "  ┌─────────────────────────────────────────────────────────────────────────────┐"
            )

            for line in feedback_lines:
                if line.strip():
                    # Wrap long lines
                    words = line.split()
                    current_line = ""
                    for word in words:
                        if len(current_line + " " + word) < 75:
                            current_line += " " + word if current_line else word
                        else:
                            padding = 77 - len(current_line)
                            print(f"  │  {current_line}{' ' * padding}│")
                            current_line = word
                    if current_line:
                        padding = 77 - len(current_line)
                        print(f"  │  {current_line}{' ' * padding}│")

            print(
                "  └─────────────────────────────────────────────────────────────────────────────┘"
            )

        print("═" * 90)

    # ============================================================================
    # UTILITY METHODS
    # ============================================================================

    def print_error(self, message: str):
        """Print error message with consistent formatting."""
        print(f"❌ {message}")

    def print_warning(self, message: str):
        """Print warning message with consistent formatting."""
        print(f"⚠️ {message}")

    def print_success(self, message: str):
        """Print success message with consistent formatting."""
        print(f"✅ {message}")

    def print_info(self, message: str):
        """Print info message with consistent formatting."""
        print(f"ℹ️ {message}")

    # ============================================================================
    # EXECUTION HEADER METHODS
    # ============================================================================

    @staticmethod
    def print_execution_header(args: argparse.Namespace):
        """
        Print a comprehensive execution header displaying all command line argument settings.

        Args:
            args: Parsed command line arguments from argparse
        """
        from datetime import datetime

        # Main header
        print("\n🚀 LINKEDIN ARTICLE GENERATOR - EXECUTION STARTED")
        print("=" * 60)

        # Execution timestamp and mode
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        execution_mode = (
            f"Parallel Mode ({args.versions} versions)"
            if args.versions > 1
            else "Single Mode"
        )

        print("📅 EXECUTION INFO:")
        print(f"  🕒 Started: {current_time}")
        print(f"  🎯 Mode: {execution_mode}")

        # Input configuration
        print("\n📝 INPUT CONFIGURATION:")

        if hasattr(args, "draft") and args.draft:
            input_type = "Command Line Draft"
            input_detail = f"{len(args.draft)} characters"
        elif hasattr(args, "file") and args.file:
            input_type = "File Input"
            input_detail = args.file
        else:
            input_type = "Default Sample"
            input_detail = "Built-in sample article"

        print(f"  📄 Source: {input_type}")
        print(f"  📏 Detail: {input_detail}")

        # Generation parameters
        print("\n🎯 GENERATION PARAMETERS:")
        print(f"  🎯 Target Score: ≥{args.target_score}%")
        print(f"  🔄 Max Iterations: {args.max_iterations}")
        print(f"  📏 Word Count Range: {args.word_count_min}-{args.word_count_max}")

        # Model configuration
        print("\n🤖 MODEL CONFIGURATION:")
        print(f"  ✍️  Generator: {args.generator_model}")
        print(f"  🎯 Judge: {args.judge_model}")
        print(f"  🌐 RAG: {args.rag_model}")
        if hasattr(args, "model") and args.model != args.generator_model:
            print(f"  🔄 Fallback: {args.model}")

        # Output settings
        print("\n💾 OUTPUT SETTINGS:")

        output_file = (
            args.output if hasattr(args, "output") and args.output else "Console Output"
        )
        export_results = (
            args.export_results
            if hasattr(args, "export_results") and args.export_results
            else "None"
        )
        export_dir = (
            args.export_dir
            if hasattr(args, "export_dir") and args.export_dir
            else "Default"
        )

        print(f"  📄 Output File: {output_file}")
        print(f"  📊 Export Results: {export_results}")
        print(f"  📁 Export Directory: {export_dir}")

        # Behavior flags
        print("\n⚙️  BEHAVIOR FLAGS:")

        verbose_status = "✅ Enabled" if args.verbose else "❌ Disabled"
        auto_status = (
            "✅ Enabled" if hasattr(args, "auto") and args.auto else "❌ Disabled"
        )
        recreate_ctx_status = (
            "✅ Enabled"
            if hasattr(args, "recreate_ctx") and args.recreate_ctx
            else "❌ Disabled"
        )
        compare_only_status = (
            "✅ Enabled"
            if hasattr(args, "compare_only") and args.compare_only
            else "❌ Disabled"
        )

        print(f"  📢 Verbose Mode: {verbose_status}")
        print(f"  🤖 Auto Mode: {auto_status}")
        print(f"  � Recreate Context: {recreate_ctx_status}")
        if args.versions > 1:
            print(f"  📊 Compare Only: {compare_only_status}")

        # Parallel mode specific info
        if args.versions > 1:
            print("\n🔀 PARALLEL MODE SETTINGS:")
            print(f"  🔢 Versions: {args.versions}")
            print("  🌡️  Temperature Range: 0.1 - 0.9 (varied creativity levels)")

        print("\n🎯 Starting LinkedIn Article Generation Process...")
        print("=" * 60)
