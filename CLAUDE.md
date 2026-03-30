# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

A DSPy-based system that transforms article drafts into polished LinkedIn articles through iterative LLM-driven generation, scoring, and improvement. It uses web research (Tavily), a 180-point scoring system, and an iterative REACT loop to reach a target quality score.

## Running the Application

```bash
# Activate virtual environment first
source venv/bin/activate

# Basic run with a draft
python main.py --draft "Your article outline here"

# From a file
python main.py --file path/to/draft.txt

# Generate multiple parallel versions for comparison
python main.py --versions 3 --file draft.txt

# Key options
python main.py --target-score 85 --max-iterations 5 --verbose --output article.md
```

Key CLI flags: `--draft/-d`, `--file/-f`, `--target-score/-t` (default 89.0), `--max-iterations/-i` (default 10), `--versions` (1-5), `--verbose/-v`, `--auto/-a` (no user interaction), `--output/-o`.

## Environment Setup

Requires a `.env` file with:
```
OPENROUTER_API_KEY="sk-or-v1-..."
TAVILY_API_KEY="tvly-dev-..."
```

Default LLM: `moonshotai/kimi-k2-thinking` via OpenRouter. Models can be overridden with `--generator-model`, `--judge-model`, `--rag-model`.

## Architecture

**Generation Loop** (in `linkedin_article_generator.py`):
1. RAG retrieval → `rag_fast.py` does async Tavily web search, packs results into token budget
2. Article generation → DSPy `ArticleGenerationSignature`
3. Scoring → `li_article_judge.py` returns 0-180 point score with category breakdown
4. If score < target: DSPy `ArticleImprovementSignature` with gap analysis, repeat
5. If score ≥ target or max iterations reached: output final article

**Scoring System** (`li_article_judge.py`, 180 points total):
- Core Thinking: 120 pts (First-Order Thinking 45pts + Strategic Deconstruction 75pts)
- Content Quality: 60 pts (Hook, Storytelling, Authority, Clarity, Value, CTA — 10pts each)
- Tiers: 89%+ World-class, 72%+ Strong, 56%+ Needs restructuring, <56% Rework

**Parallel Versions** (`main.py`): Uses DSPy's Parallel module with temperatures [0.1, 0.5, 0.9, 0.3, 0.7] per version slot. All versions run independently, then user selects best.

**Key modules:**
- `main.py` — CLI, orchestration, parallel execution
- `linkedin_article_generator.py` — Core iterative generation loop
- `li_article_judge.py` — Comprehensive scoring with fact-checking
- `rag_fast.py` — Async web search and context packing
- `dspy_factory.py` — OpenRouter model resolution and DSPy LM creation
- `models.py` — Pydantic models: `ArticleVersion`, `JudgementModel`, `ArticleScoreModel`
- `context_window_manager.py` — Token budget: 40% instructions / 30% RAG / 30% safety
- `word_count_manager.py` — Enforces 2000-2500 word range with strategic guidance
- `output_manager.py` — Console output formatting for single and parallel modes
- `progress_dashboard.py` — Score tier translation and progress visualization

## DSPy Patterns

Signatures are defined with `dspy.Signature` classes. The main ones are `ArticleGenerationSignature` and `ArticleImprovementSignature` in `linkedin_article_generator.py`. Modules use `dspy.ChainOfThought` or `dspy.Predict`. Model setup via `dspy.configure(lm=...)` happens in `main.py` before any module instantiation.

## Dependencies

Install with: `pip install -r requirements.txt`

Key packages: `dspy`, `pydantic`, `python-dotenv`, `tavily-python`, `ddgs`, `beautifulsoup4`, `mlflow`, `attachments`.
