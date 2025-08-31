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

import dspy
import argparse
import sys
from pathlib import Path

from linkedin_article_generator import LinkedInArticleGenerator
from dspy_factory import get_openrouter_model, DspyModelConfig
from li_judge_simple import print_score_report
from datetime import datetime
from typing import Dict, Any

import mlflow

# Default model constant for fallback
DEFAULT_MODEL_NAME = "moonshotai/kimi-k2:free"

current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
mlflow.set_experiment(f"DSPy LinkedIn {current_time}")
mlflow.dspy.autolog()


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


def resolve_model(
    model_name: str, default_model: str, default_constant: str, temp: float = 0.0
) -> DspyModelConfig:
    """
    Resolve a model using cascading fallback logic:
    1. Try get_openrouter_model(model_name)
    2. If None, try get_openrouter_model(default_model)
    3. If None, try get_openrouter_model(default_constant)
    4. If None, raise appropriate error

    Args:
        model_name: The primary model to try
        default_model: The fallback model from --model argument
        default_constant: The constant DEFAULT_MODEL_NAME

    Returns:
        DspyModelConfig with resolved model configuration

    Raises:
        RuntimeError: If no models can be resolved
    """
    # Try the primary model first
    model_config = get_openrouter_model(model_name, temp=temp)
    if model_config is not None:
        return model_config

    print(
        f"⚠️  Model '{model_name}' not found, falling back to default model '{default_model}'"
    )

    # Try the default model
    model_config = get_openrouter_model(default_model)
    if model_config is not None:
        return model_config

    print(
        f"⚠️  Default model '{default_model}' not found, falling back to constant '{default_constant}'"
    )

    # Try the constant default
    model_config = get_openrouter_model(default_constant)
    if model_config is not None:
        return model_config

    # If all fail, raise an error
    raise RuntimeError(
        f"❌ Unable to resolve any model. Tried:\n"
        f"  1. Primary model: '{model_name}'\n"
        f"  2. Default model: '{default_model}'\n"
        f"  3. Constant model: '{default_constant}'\n"
        f"Please check your OpenRouter API key and model names."
    )


def main():
    """Main entry point for the LinkedIn Article Generator."""
    parser = argparse.ArgumentParser(
        description="Generate world-class LinkedIn articles using DSPy REACT with intelligent web search and iterative improvement",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python main.py
  python main.py --draft "AI is transforming business..."
  python main.py --file draft.txt
  
  # Configuration options
  python main.py --target-score 85 --max-iterations 5
  python main.py --output generated_article.md
  
  # Component-specific model selection
  python main.py --generator-model "anthropic/claude-3-sonnet" \\
                 --judge-model "openai/gpt-4o" \\
                 --rag-model "moonshotai/kimi-k2:free"

The system will:
1. Generate an initial article from your draft/outline
2. Score it using comprehensive LinkedIn criteria
3. Iteratively improve until target score (≥89%) is achieved
4. Display progress and final results

Model Selection:
  --generator-model: Model for article generation (default: moonshotai/kimi-k2:free)
  --judge-model: Model for article scoring (default: deepseek/deepseek-r1-0528:free)
  --rag-model: Model for web search/retrieval (default: deepseek/deepseek-r1-0528:free)

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
        help="Maximum number of improvement iterations (default: 10, minimum: 1)",
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
        default="moonshotai/kimi-k2:free",
        help="Default model to use if specialized models are not found (default: %(default)s)",
    )
    parser.add_argument(
        "--generator-model",
        default="moonshotai/kimi-k2:free",
        help="LLM model to use for article generation components (default: %(default)s)",
    )
    parser.add_argument(
        "--judge-model",
        default="deepseek/deepseek-r1-0528:free",
        help="LLM model to use for article scoring components (default: %(default)s)",
    )
    parser.add_argument(
        "--rag-model",
        default="deepseek/deepseek-r1-0528:free",
        help="LLM model to use for RAG retrieval components (default: %(default)s)",
    )
    parser.add_argument(
        "--output", "-o", help="Output file path for the generated article"
    )
    parser.add_argument("--export-results", help="Export detailed results to JSON file")
    parser.add_argument(
        "--recreate-ctx",
        action="store_true",
        default=False,
        help="Regenerate RAG context for each article version (default: False - reuse initial context)",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress progress messages"
    )
    parser.add_argument(
        "--auto",
        "-a",
        action="store_true",
        help="Run in automatic mode without user interaction (default: False)",
    )

    args = parser.parse_args()

    # Validate max_iterations is at least 1
    if args.max_iterations < 1:
        print("❌ Error: max-iterations must be at least 1")
        sys.exit(1)

    try:
        # Resolve all models using cascading fallback logic
        if not args.quiet:
            print(f"🔍 Resolving models with fallback logic...")

        try:
            resolved_generator = resolve_model(
                args.generator_model, args.model, DEFAULT_MODEL_NAME, temp=0.5
            )
            resolved_judge = resolve_model(
                args.judge_model, args.model, DEFAULT_MODEL_NAME
            )
            resolved_rag = resolve_model(args.rag_model, args.model, DEFAULT_MODEL_NAME)
        except RuntimeError as e:
            print(f"{e}")
            sys.exit(1)

        models = {
            "generator": resolved_generator,
            "judge": resolved_judge,
            "rag": resolved_rag,
        }

        # Setup DSPy with the resolved generator model
        if not args.quiet:
            print(
                f"🤖 Setting up DSPy with resolved generator model: {resolved_generator.name}"
            )
        dspy.configure(lm=resolved_generator.dspy_lm)

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

        # Display resolved model configuration if not quiet
        if not args.quiet:
            print(f"🔧 Resolved Model Configuration:")
            print(
                f"   Generator: {models['generator'].name}, Temp: 0.5, max_output_tokens: {models['generator'].max_output_tokens} "
            )
            print(
                f"   Judge: {models['judge'].name}, Temp: 0.0, max_output_tokens: {models['judge'].max_output_tokens} "
            )
            print(
                f"   RAG: {models['rag'].name}, Temp: 0.0, max_output_tokens: {models['rag'].max_output_tokens} "
            )

        # Initialize Article Generator with component-specific models
        generator = LinkedInArticleGenerator(
            target_score_percentage=args.target_score,
            max_iterations=args.max_iterations,
            word_count_min=args.word_count_min,
            word_count_max=args.word_count_max,
            models=models,
            recreate_ctx=args.recreate_ctx,
            auto=args.auto,
        )

        if not args.quiet:
            print(f"🎯 Target score: ≥{args.target_score}%")
            print(f"🔄 Max iterations: {args.max_iterations}")
            print(f"📏 Word count range: {args.word_count_min}-{args.word_count_max}")

        # Generate article
        result = generator.generate_article(draft_text, verbose=not args.quiet)

        # Print detailed scoring report
        print_score_report(result["final_score"])

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
            # dspy.inspect_history(1)  # Inspect history for debugging
        sys.exit(1)


if __name__ == "__main__":
    main()
