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
import asyncio
import time

from linkedin_article_generator import LinkedInArticleGenerator
from dspy_factory import get_openrouter_model, DspyModelConfig
from datetime import datetime
from typing import Dict, Any, List, Optional
from output_manager import OutputManager
from attachments import Attachments
from attachments.data import get_sample_path

import mlflow

# Default model constant for fallback
DEFAULT_MODEL_NAME = "moonshotai/kimi-k2-thinking"

current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
mlflow.set_experiment(f"DSPy LinkedIn {current_time}")
mlflow.dspy.autolog()  # type: ignore # Automatically log DSPy runs to MLflow


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


def create_parallel_generators(
    args: argparse.Namespace, base_models: Dict[str, DspyModelConfig], num_versions: int
) -> List[LinkedInArticleGenerator]:
    """
    Create multiple LinkedInArticleGenerator instances with different temperature settings.

    Args:
        args: Parsed command line arguments
        base_models: Base model configurations (generator, judge, rag)
        num_versions: Number of parallel versions to create

    Returns:
        List of configured LinkedInArticleGenerator instances
    """
    generators = []

    # Temperature settings for variety (same model, different creativity levels)
    temperatures = [0.1, 0.5, 0.9]  # Focused, Standard, Creative
    if num_versions > 3:
        # Add more variations if more versions requested
        temperatures.extend([0.3, 0.7][: num_versions - 3])

    for i, temp in enumerate(temperatures[:num_versions]):
        # Create model config with different temperature for generator only
        version_models = base_models.copy()
        generator_model = get_openrouter_model(args.generator_model, temp=temp)
        if generator_model is None:
            print(
                f"⚠️ Failed to create model config for temperature {temp}, skipping version {i+1}"
            )
            continue
        version_models["generator"] = generator_model

        # Create generator instance
        generator = LinkedInArticleGenerator(
            writer_id=i + 1,
            target_score_percentage=args.target_score,
            max_iterations=args.max_iterations,
            word_count_min=args.word_count_min,
            word_count_max=args.word_count_max,
            models=version_models,
            verbose=args.verbose,
            recreate_ctx=args.recreate_ctx,
            auto=True,  # Force auto mode for parallel execution
            export_dir=args.export_dir,
        )

        generators.append(generator)

    return generators


def run_parallel_generation(
    generators: List[LinkedInArticleGenerator], draft_text: str, verbose: bool
) -> List[Dict[str, Any]]:
    """
    Run multiple generators in parallel using DSPy's built-in Parallel module.

    Args:
        generators: List of LinkedInArticleGenerator instances
        draft_text: The article draft text

    Returns:
        List of result dictionaries with success/failure status
    """

    # Use DSPy's built-in parallel execution
    parallel = dspy.Parallel(num_threads=len(generators))

    # Prepare parallel execution calls
    parallel_calls = []
    for i, generator in enumerate(generators):
        version_num = i + 1

        # Create a wrapper function for each generator
        def make_generate_call(gen, draft, version_num=version_num):
            def generate_call():
                try:

                    start_time = time.time()
                    result = gen.generate_article(
                        draft, verbose=verbose, version_id=version_num
                    )
                    generation_time = time.time() - start_time

                    # Print version completion message
                    final_score = result.get("final_score")
                    score_value = final_score.percentage if final_score else None

                    return {
                        "version": version_num,
                        "success": True,
                        "result": result,
                        "generation_time": generation_time,
                        "temperature": getattr(
                            gen.models["generator"], "temperature", 0.5
                        ),
                    }
                except Exception as e:
                    return {
                        "version": version_num,
                        "success": False,
                        "error": str(e),
                        "temperature": getattr(
                            gen.models["generator"], "temperature", 0.5
                        ),
                    }

            return generate_call

        parallel_calls.append((make_generate_call(generator, draft_text), {}))

    # Execute in parallel using DSPy's Parallel module
    parallel_results = parallel(parallel_calls)

    # Extract results from DSPy's parallel execution format
    results = []
    for result in parallel_results:
        if callable(result):
            # If result is still callable, execute it
            results.append(result())
        else:
            results.append(result)

    return results


def display_version_comparison(results: List[Dict[str, Any]]) -> None:
    """
    Display a comparison table of all generated versions.

    Args:
        results: List of generation results
    """
    # Use OutputManager for consistent formatting
    output_manager = OutputManager(writer_id=1, version_id=1, verbose=True)
    output_manager.display_version_comparison(results)


def select_best_version(results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Interactive prompt to select the best version from successful results.

    Args:
        results: List of generation results

    Returns:
        Selected result dictionary
    """
    successful_results = [r for r in results if r["success"]]

    if not successful_results:
        print("❌ No successful versions to select from")
        return None

    if len(successful_results) == 1:
        print("✅ Only one successful version - selecting it automatically")
        return successful_results[0]

    print("\n🎯 SELECT BEST VERSION")
    print("-" * 50)

    while True:
        try:
            choice = (
                input(
                    f"Enter version number (1-{len(successful_results)}) or 'best' for highest score: "
                )
                .strip()
                .lower()
            )

            if choice == "best":
                # Select version with highest score
                best_result = max(
                    successful_results,
                    key=lambda r: r["result"]["final_score"].percentage,
                )
                print(
                    f"✅ Selected version {best_result['version']} (highest score: {best_result['result']['final_score'].percentage:.1f}%)"
                )
                return best_result

            version_num = int(choice)
            if 1 <= version_num <= len(successful_results):
                selected_result = successful_results[version_num - 1]
                print(f"✅ Selected version {selected_result['version']}")
                return selected_result
            else:
                print(
                    f"❌ Please enter a number between 1 and {len(successful_results)}, or 'best'"
                )

        except ValueError:
            print("❌ Please enter a valid number or 'best'")
        except KeyboardInterrupt:
            print("\n❌ Selection cancelled")
            return successful_results[0]  # Return first successful version


def main():
    """Main entry point for the LinkedIn Article Generator."""

    # Initialize variables for parallel mode
    results = None
    selected_result = None
    generator = None

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
                 --rag-model "moonshotai/kimi-k2-thinking"

The system will:
1. Generate an initial article from your draft/outline
2. Score it using comprehensive LinkedIn criteria
3. Iteratively improve until target score (≥89%) is achieved
4. Display progress and final results

Model Selection:
  --generator-model: Model for article generation (default: moonshotai/kimi-k2-thinking)
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
        default="moonshotai/kimi-k2-thinking",
        help="Default model to use if specialized models are not found (default: %(default)s)",
    )
    parser.add_argument(
        "--generator-model",
        default="moonshotai/kimi-k2-thinking",
        # default="deepseek/deepseek-r1-0528:free",
        help="LLM model to use for article generation components (default: %(default)s)",
    )
    parser.add_argument(
        "--judge-model",
        default="google/gemini-3-flash-preview",
        help="LLM model to use for article scoring components (default: %(default)s)",
    )
    parser.add_argument(
        "--rag-model",
        default="moonshotai/kimi-k2-thinking",
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
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Print verbose progress messages",
    )
    parser.add_argument(
        "--auto",
        "-a",
        action="store_true",
        help="Run in automatic mode without user interaction (default: False)",
    )
    parser.add_argument(
        "--export-dir",
        help="Directory name to save all generated versions to (automatic numbering if exists). Defaults to versions-YYYYMMDD_HHMMSS",
        default=f"versions-{current_time}",
    )

    # Parallel execution options
    parser.add_argument(
        "--versions",
        type=int,
        default=1,
        choices=range(1, 6),
        metavar="[1-5]",
        help="Number of parallel versions to generate (default: 1, max: 5)",
    )
    parser.add_argument(
        "--compare-only",
        action="store_true",
        help="Show version comparison without interactive selection prompt",
    )

    args = parser.parse_args()

    # Validate max_iterations is at least 1
    if args.max_iterations < 1:
        print("❌ Error: max-iterations must be at least 1")
        sys.exit(1)

    # Print execution header with all command line settings
    OutputManager.print_execution_header(args)

    try:
        # Resolve all models using cascading fallback logic
        if args.verbose:
            print(f"🔍 Resolving models with fallback logic...")

        try:
            resolved_generator = resolve_model(
                args.generator_model,
                args.model,
                DEFAULT_MODEL_NAME,
                temp=0.5,
            )
            resolved_judge = resolve_model(
                args.judge_model,
                args.model,
                DEFAULT_MODEL_NAME,
            )
            resolved_rag = resolve_model(
                args.rag_model,
                args.model,
                DEFAULT_MODEL_NAME,
            )
        except RuntimeError as e:
            print(f"{e}")
            sys.exit(1)

        models = {
            "generator": resolved_generator,
            "judge": resolved_judge,
            "rag": resolved_rag,
        }

        # Setup DSPy with the resolved generator model for thread-safe parallel execution
        if args.verbose:
            print(
                f"🤖 Setting up DSPy with resolved generator model: {resolved_generator.name}"
            )
        dspy.configure(
            lm=resolved_generator.dspy_lm,
            async_max_workers=4,
        )
        # dspy.enable_litellm_logging()

        # Get article draft
        if args.draft:
            draft_text = args.draft
            if args.verbose:
                print(f"📝 Using provided draft ({len(draft_text)} characters)")
        elif args.file:
            file_path = get_sample_path(args.file)
            draft_text = Attachments(file_path)
            draft_text = draft_text.text

            if args.verbose:
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

            if args.verbose:
                print("📝 No draft provided, using sample article outline")
                print(f"📝 Sample length: {len(draft_text)} characters")

        # Validate draft
        if not draft_text or len(draft_text.strip()) < 50:
            print("❌ Error: Article draft is too short (minimum 50 characters)")
            sys.exit(1)

        # Display resolved model configuration if verbose
        if args.verbose:
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

        """director_ideas = await asyncio.gather(
            *[self.genDirectorCut.acall(video_idea=video_idea, director=director) 
                for director in all_directors]"""

        # Check if parallel mode is requested
        if args.versions > 1:
            if args.verbose:
                print(
                    f"🔀 PARALLEL MODE: Generating {args.versions} versions with different temperature settings"
                )
                print(f"🎯 Target score: ≥{args.target_score}%")
                print(f"🔄 Max iterations: {args.max_iterations}")
                print(
                    f"📏 Word count range: {args.word_count_min}-{args.word_count_max}"
                )

            # Create parallel generators
            generators = create_parallel_generators(args, models, args.versions)

            if not generators:
                print("❌ Failed to create any generators")
                sys.exit(1)

            if args.verbose:
                print(
                    f"🤖 Created {len(generators)} generators with temperatures: {[getattr(g.models['generator'], 'temp', 0.5) for g in generators]}"
                )

            # Run parallel generation
            if args.verbose:
                print("🚀 Starting parallel generation...")

            results = run_parallel_generation(
                generators, draft_text, verbose=args.verbose
            )

            # Display comparison
            display_version_comparison(results)

            # Select best version (unless compare-only mode)
            if args.compare_only:
                print("📊 Compare-only mode: exiting without selection")
                successful_count = len([r for r in results if r["success"]])
                if successful_count > 0:
                    sys.exit(0)
                else:
                    sys.exit(1)

            selected_result = select_best_version(results)

            if selected_result is None:
                print("❌ No successful versions to select from")
                sys.exit(1)

            # Use selected result as the final result
            result = selected_result["result"]
            if args.verbose:
                print(
                    f"✅ Using version {selected_result['version']} (Score: {result['final_score'].percentage:.1f}%, Temp: {selected_result['temperature']})"
                )

        else:
            # Single generator mode (existing logic)
            if args.verbose:
                print(f"🎯 Target score: ≥{args.target_score}%")
                print(f"🔄 Max iterations: {args.max_iterations}")
                print(
                    f"📏 Word count range: {args.word_count_min}-{args.word_count_max}"
                )

            # Initialize Article Generator with component-specific models
            generator = LinkedInArticleGenerator(
                writer_id=1,
                target_score_percentage=args.target_score,
                max_iterations=args.max_iterations,
                word_count_min=args.word_count_min,
                word_count_max=args.word_count_max,
                models=models,
                verbose=args.verbose,
                recreate_ctx=args.recreate_ctx,
                auto=args.auto,
                export_dir=args.export_dir,
            )

            # Generate article
            result = generator.generate_article(draft_text)

        # Print detailed scoring report or dashboard based on verbose mode
        if args.verbose:
            # In verbose mode, show the progress dashboard instead of full report
            from progress_dashboard import ProgressDashboard

            dashboard = ProgressDashboard()
            final_dashboard = dashboard.generate_progress_dashboard(
                current_score=result["final_score"].percentage,
                target_score=args.target_score,
                word_count=result["word_count"],
                target_range=(args.word_count_min, args.word_count_max),
                overall_feedback=result["final_score"].overall_feedback,
            )
            print(final_dashboard)
        else:
            # Use OutputManager for score reporting with version header
            output_manager = OutputManager(
                writer_id=result["writer_id"],
                version_id=result["iterations_used"],
                verbose=args.verbose,
            )
            output_manager.print_score_report(result["final_score"])

        # Always handle final article output - either save to file or display
        if args.output:
            # Save to specified file
            save_article(result["final_article"], args.output)
        else:
            # Display to screen (both verbose and non-verbose modes)
            print("\n" + "=" * 80)
            print("📄 FINAL GENERATED ARTICLE")
            print("=" * 80)
            print(result["final_article"])
            print("\n" + "=" * 80)

        # Export detailed results if specified
        if args.export_results:
            if args.versions > 1:
                # In many verions mode, we don't have a single generator instance
                # Export the selected result data instead
                import json

                # Get the selected result and results from the parallel execution
                selected_version = None
                all_results_data = []

                if "selected_result" in locals() and selected_result is not None:
                    selected_version = selected_result["version"]

                if results is not None:
                    all_results_data = [
                        {
                            "version": r["version"],
                            "success": r["success"],
                            "score": (
                                r["result"]["final_score"].percentage
                                if r["success"]
                                else None
                            ),
                            "word_count": (
                                r["result"]["word_count"] if r["success"] else None
                            ),
                            "generation_time": (
                                r["generation_time"] if r["success"] else None
                            ),
                            "temperature": r["temperature"],
                        }
                        for r in results
                    ]

                export_data = {
                    "parallel_mode": True,
                    "selected_version": selected_version,
                    "final_result": result,
                    "all_results": all_results_data,
                }
                with open(args.export_results, "w", encoding="utf-8") as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                if args.verbose:
                    print(f"📊 Parallel results exported to: {args.export_results}")
            else:
                # Single mode - use the generator instance
                if generator is not None:
                    generator.export_results(args.export_results)
                    if args.verbose:
                        print(f"📊 Detailed results exported to: {args.export_results}")

        # Exit with appropriate code based on results
        if result["target_achieved"]:
            if args.verbose:
                print("✅ Success: Article achieved world-class status!")
            sys.exit(0)
        else:
            final_score = result["final_score"].percentage
            if final_score >= 72:
                if args.verbose:
                    print("⚠️  Warning: Article is strong but could be improved")
                sys.exit(0)
            else:
                if args.verbose:
                    print("❌ Article needs significant improvement before publishing")
                sys.exit(0)

    except KeyboardInterrupt:
        print("\n❌ Generation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Error during generation: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
            # dspy.inspect_history(1)  # Inspect history for debugging
        sys.exit(1)


if __name__ == "__main__":
    main()
