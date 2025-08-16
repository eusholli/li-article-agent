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

from li_article_judge import LinkedInArticleScorer, ArticleScoreModel
from criteria_extractor import CriteriaExtractor
from word_count_manager import WordCountManager
from rag import TavilyRetriever


@dataclass
class ArticleVersion:
    """Represents a version of an article with its metadata."""

    version: int
    content: str
    word_count: int
    score_results: Optional[ArticleScoreModel] = None
    improvement_feedback: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class ArticleGenerationSignature(dspy.Signature):
    """Generate a complete LinkedIn article from draft/outline with RAG context and markdown formatting."""

    draft_or_outline = dspy.InputField(desc="Original draft or outline to expand")
    original_draft = dspy.InputField(
        desc="Original draft for reference to maintain key points"
    )
    context = dspy.InputField(
        desc="Dictionary mapping URLs to their text content for citation selection. Key: URL, Value: relevant text content",
        default={},
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
        
        CITATION CONTROL:
        - ONLY use citations that appear in the provided RAG context
        - Copy citation format exactly: [text](url)
        - DO NOT create new external references or links
        - Present uncited content as your own analysis/opinion
        - Maintain clear distinction between cited facts and personal insights
        
        CONTENT REQUIREMENTS:
        - Expand the draft/outline into a comprehensive LinkedIn article
        - Target 2000-2500 words of actual content (excluding markdown syntax)
        - Maintain professional LinkedIn tone and structure
        - Objective and third-person, with a more structured, business/technical tone
        - Address all key points from the original draft"""
    )


class ArticleImprovementSignature(dspy.Signature):
    """Improve an existing article based on scoring feedback and criteria while maintaining consistency with original draft."""

    current_article = dspy.InputField(desc="Current version of the article")
    original_draft = dspy.InputField(
        desc="Original draft for reference to maintain key points"
    )
    context = dspy.InputField(
        desc="Dictionary mapping URLs to their text content for citation selection. Key: URL, Value: relevant text content",
        default={},
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
        
        CITATION CONTROL:
        - ONLY use citations that appear in the provided RAG context
        - Copy citation format exactly: [text](url)
        - DO NOT create new external references or links
        - Present uncited content as your own analysis/opinion
        - Maintain clear distinction between cited facts and personal insights
        
        CONTENT REQUIREMENTS:
        - Address the scoring feedback while maintaining original draft key points
        - Target 2000-2500 words of actual content (excluding markdown syntax)
        - Maintain professional LinkedIn tone and structure"""
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
        target_score_percentage: float = 89.0,
        max_iterations: int = 10,
        word_count_min: int = 2000,
        word_count_max: int = 2500,
    ):
        """
        Initialize the LinkedIn Article Generator.

        Args:
            target_score_percentage: Target score percentage for world-class articles
            max_iterations: Maximum number of improvement iterations
            word_count_min: Minimum target word count
            word_count_max: Maximum target word count
        """
        self.target_score_percentage = target_score_percentage
        self.max_iterations = max_iterations

        # Initialize components
        self.rag = TavilyRetriever(k=10)  # Use TavilyRetriever for web search
        self.judge = LinkedInArticleScorer()
        self.criteria_extractor = CriteriaExtractor()
        self.word_count_manager = WordCountManager(word_count_min, word_count_max)

        # Initialize DSPy modules
        self.generator = dspy.ChainOfThought(ArticleGenerationSignature)
        self.improver = dspy.ChainOfThought(ArticleImprovementSignature)

        # Track generation history
        self.versions: List[ArticleVersion] = []
        self.generation_log: List[str] = []
        self.original_draft: Optional[str] = None
        self.search_context: Dict[str, str] = {}

    def generate_article(
        self, draft_or_outline: str, verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a world-class LinkedIn article from a draft or outline.

        Args:
            draft_or_outline: Initial draft article or outline
            verbose: Whether to print progress updates

        Returns:
            Dict containing final article, score, and generation metadata
        """
        return self.generate_article_with_context(draft_or_outline, {}, verbose)

    def generate_article_with_context(
        self, draft_or_outline: str, context: Dict[str, str] = {}, verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a world-class LinkedIn article from a draft or outline with web context.

        Args:
            draft_or_outline: Initial draft article or outline
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
        self.original_draft = draft_or_outline
        self.search_context = context or {}

        if context and verbose:
            print(f"🌐 Using web context: {len(context)} URLs")

        # Generate initial markdown article from draft/outline (Version 1)
        if verbose:
            print(f"📝 Generating initial markdown article from draft...")

        initial_article = self._generate_initial_article(
            draft_or_outline, context, verbose
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
        """Run the iterative improvement process."""
        current_article = initial_article
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1

            if verbose:
                print(f"\n🔄 Iteration {iteration}: Scoring and Analysis")
                print("-" * 40)

            # Score current article
            score_results = self.judge(current_article)

            # Update current version with score
            if self.versions:
                self.versions[-1].score_results = score_results

            current_percentage = score_results.percentage

            if verbose:
                print(
                    f"📊 Current Score: {score_results.total_score}/{self.criteria_extractor.get_total_possible_score()} ({current_percentage:.1f}%)"
                )
                print(f"🎯 Target Score: ≥{self.target_score_percentage}%")

            # Check if target achieved
            if current_percentage >= self.target_score_percentage:
                if verbose:
                    print(f"🎉 TARGET ACHIEVED! Article reached world-class status!")

                self.generation_log.append(
                    f"Iteration {iteration}: Target achieved ({current_percentage:.1f}%)"
                )
                break

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
                current_article, score_results, improvement_analysis
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
        final_score_results = self.judge(current_article)
        if self.versions:
            self.versions[-1].score_results = final_score_results

        # Prepare final result
        final_result = {
            "final_article": current_article,
            "final_score": final_score_results,
            "target_achieved": final_score_results.percentage
            >= self.target_score_percentage,
            "iterations_used": iteration,
            "versions": self.versions,
            "generation_log": self.generation_log,
            "word_count": self.word_count_manager.count_words(current_article),
            "improvement_summary": self._generate_improvement_summary(),
        }

        return final_result

    def _generate_initial_article(
        self, draft_or_outline: str, context: Dict[str, str], verbose: bool
    ) -> str:
        """Generate initial markdown article from draft/outline using ArticleGenerationSignature."""

        # Prepare generation inputs
        scoring_criteria = self.criteria_extractor.get_criteria_for_generation()
        word_count_guidance = self.word_count_manager.get_length_optimization_prompt(
            self.word_count_manager.target_optimal
        )

        try:
            # Generate initial article with RAG context
            result = self.generator(
                draft_or_outline=draft_or_outline,
                original_draft=draft_or_outline,
                context=context,
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
        gap_analysis = self.criteria_extractor.analyze_score_gaps(score_results)

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
    ) -> str:
        """Generate an improved version of the article while maintaining consistency with original draft."""

        # Prepare improvement inputs
        scoring_criteria = self.criteria_extractor.get_criteria_for_generation()
        word_count_guidance = self.word_count_manager.get_length_optimization_prompt(
            self.word_count_manager.count_words(current_article), score_results
        )

        # Generate improved article with original draft context
        result = self.improver(
            current_article=current_article,
            original_draft=self._get_original_draft(),
            context=self.search_context,
            score_feedback=improvement_analysis["detailed_feedback"],
            scoring_criteria=scoring_criteria,
            word_count_guidance=word_count_guidance,
            improvement_focus=improvement_analysis["focus_summary"],
        )

        return result.improved_article

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
    # Example usage
    generator = LinkedInArticleGenerator()

    sample_draft = """
    # The Future of AI in Business
    
    AI is transforming how businesses operate. Companies need to adapt or risk being left behind.
    
    Key areas:
    - Automation of routine tasks
    - Better customer insights
    - Improved decision making
    
    Challenges include data privacy and employee training.
    """

    print("Testing LinkedIn Article Generator with sample draft...")
    result = generator.generate_article(sample_draft, verbose=True)

    print(
        f"\nGeneration completed. Final article length: {len(result['final_article'])} characters"
    )
