#!/usr/bin/env python3
"""
LinkedIn Article Generator - Main Entry Point

This script demonstrates how to use the LinkedIn Article REACT system
to create world-class LinkedIn articles from drafts or outlines using
intelligent web search and context integration.

Usage:
    python main.py
    python main.py --draft "Your article draft here"
    python main.py --file path/to/draft.txt
    python main.py --target-score 85 --max-iterations 5
"""

import argparse
import sys
from pathlib import Path

from linkedin_article_react import LinkedInArticleREACT
from dspy_factory import setup_dspy_provider


def read_file(filepath: str) -> str:
    """Read article draft from a file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"❌ Error: File '{filepath}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error reading file '{filepath}': {e}")
        sys.exit(1)


def save_article(article: str, filepath: str):
    """Save the generated article to a file."""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(article)
        print(f"💾 Article saved to: {filepath}")
    except Exception as e:
        print(f"❌ Error saving article: {e}")


def main():
    """Main entry point for the LinkedIn Article Generator."""
    parser = argparse.ArgumentParser(
        description="Generate world-class LinkedIn articles using DSPy REACT with intelligent web search and iterative improvement",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py
  python main.py --draft "AI is transforming business..."
  python main.py --file draft.txt
  python main.py --target-score 85 --max-iterations 5
  python main.py --model "openrouter/anthropic/claude-3-haiku"
  python main.py --output generated_article.md

The REACT system will:
1. Analyze your draft to determine if web research is needed
2. Search the web for relevant context if beneficial
3. Generate an initial article with enhanced context
4. Score it using comprehensive LinkedIn criteria
5. Iteratively improve until target score (≥89%) is achieved
6. Display progress and final results with REACT metadata

Target Scores:
  89%+: World-class — publish as is
  72%+: Strong, but tighten weak areas  
  56%+: Needs restructuring and sharper insights
  <56%: Rework before publishing
        """,
    )

    # Input options
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--draft", "-d", help="Article draft or outline text (enclose in quotes)"
    )
    input_group.add_argument(
        "--file", "-f", help="Path to file containing the article draft or outline"
    )

    # Generation parameters
    parser.add_argument(
        "--target-score",
        "-t",
        type=float,
        default=89.0,
        help="Target score percentage for world-class articles (default: 89.0)",
    )
    parser.add_argument(
        "--max-iterations",
        "-i",
        type=int,
        default=10,
        help="Maximum number of improvement iterations (default: 10)",
    )
    parser.add_argument(
        "--word-count-min",
        type=int,
        default=2000,
        help="Minimum target word count (default: 2000)",
    )
    parser.add_argument(
        "--word-count-max",
        type=int,
        default=2500,
        help="Maximum target word count (default: 2500)",
    )

    # Model and output options
    parser.add_argument(
        "--model",
        "-m",
        default="openrouter/moonshotai/kimi-k2:free",
        help="LLM model to use (default: %(default)s)",
    )
    parser.add_argument(
        "--output", "-o", help="Output file path for the generated article"
    )
    parser.add_argument("--export-results", help="Export detailed results to JSON file")
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress progress messages"
    )

    args = parser.parse_args()

    try:
        # Setup DSPy provider
        if not args.quiet:
            print(f"🤖 Setting up DSPy with model: {args.model}")
        setup_dspy_provider(args.model)

        # Get article draft
        if args.draft:
            draft_text = args.draft
            if not args.quiet:
                print(f"📝 Using provided draft ({len(draft_text)} characters)")
        elif args.file:
            draft_text = read_file(args.file)
            if not args.quiet:
                print(f"📄 Loaded draft from: {args.file}")
                print(f"📝 Draft length: {len(draft_text)} characters")
        else:
            # Interactive mode - use default sample
            draft_text = """
# The Future of Remote Work

Remote work has fundamentally changed how we think about productivity and collaboration.

Key benefits:
- Increased flexibility for employees
- Access to global talent pool
- Reduced overhead costs
- Better work-life balance

Challenges:
- Communication barriers
- Maintaining company culture
- Managing distributed teams
- Technology infrastructure needs

The future will likely be hybrid, combining the best of both worlds.
            """.strip()

            if not args.quiet:
                print("📝 No draft provided, using sample article outline")
                print(f"📝 Sample length: {len(draft_text)} characters")

        # Validate draft
        if not draft_text or len(draft_text.strip()) < 50:
            print("❌ Error: Article draft is too short (minimum 50 characters)")
            sys.exit(1)

        # Initialize REACT generator
        generator = LinkedInArticleREACT(
            target_score_percentage=args.target_score,
            max_iterations=args.max_iterations,
            word_count_min=args.word_count_min,
            word_count_max=args.word_count_max,
        )

        if not args.quiet:
            print(f"🎯 Target score: ≥{args.target_score}%")
            print(f"🔄 Max iterations: {args.max_iterations}")
            print(f"📏 Word count range: {args.word_count_min}-{args.word_count_max}")

        # Generate article
        result = generator.generate_article(draft_text, verbose=not args.quiet)

        # Save article if output path specified
        if args.output:
            save_article(result["final_article"], args.output)

        # Export detailed results if specified
        if args.export_results:
            generator.export_results(args.export_results)
            if not args.quiet:
                print(f"📊 Detailed results exported to: {args.export_results}")

        # Print final article if not quiet and no output file
        if not args.quiet and not args.output:
            print("\n" + "=" * 80)
            print("📄 FINAL GENERATED ARTICLE")
            print("=" * 80)
            print(result["final_article"])
            print("\n" + "=" * 80)

        # Exit with appropriate code based on results
        if result["target_achieved"]:
            if not args.quiet:
                print("✅ Success: Article achieved world-class status!")
            sys.exit(0)
        else:
            final_score = result["final_score"].percentage
            if final_score >= 72:
                if not args.quiet:
                    print("⚠️  Warning: Article is strong but could be improved")
                sys.exit(1)
            else:
                if not args.quiet:
                    print("❌ Article needs significant improvement before publishing")
                sys.exit(2)

    except KeyboardInterrupt:
        print("\n❌ Generation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Error during generation: {e}")
        if not args.quiet:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
