"""
LinkedIn Article Generator — REST API

Exposes article generation as a streaming Server-Sent Events (SSE) endpoint.
The client receives real-time progress events and a final result event when done.

Event types emitted on the SSE stream:
  {"type": "progress", "stage": "<stage>", "message": "<text>"}
  {"type": "heartbeat"}
  {"type": "complete", "article": {"original": "...", "humanized": "..."}, "score": {...}, "target_achieved": bool, "iterations_used": int}
  {"type": "error", "message": "<text>"}

Usage:
  uvicorn api:app --host 0.0.0.0 --port 8000 --workers 1
"""

import asyncio
import datetime
import json
import logging
import queue
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("li_api")

import dspy
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from api_models import GenerateRequest
from linkedin_article_generator import LinkedInArticleGenerator
from model_cache import API_DEFAULT_MODEL_NAME, get_cached_model, resolve_model_cached
from output_manager import OutputManager

# Thread pool for blocking generation work.
# workers=1 is safe with the in-process job model; increase for higher concurrency.
_executor = ThreadPoolExecutor(max_workers=4)


# ---------------------------------------------------------------------------
# QueueOutputManager — forwards progress events into a thread-safe queue
# ---------------------------------------------------------------------------


class QueueOutputManager(OutputManager):
    """
    Subclass of OutputManager that routes progress messages into a queue
    instead of printing to stdout.  The SSE event_stream coroutine reads
    from this queue and forwards events to the HTTP client.
    """

    def __init__(self, writer_id: int, progress_queue: queue.Queue):
        super().__init__(writer_id, version_id=1, verbose=False)
        self._q = progress_queue

    def _emit(self, stage: str, message: str) -> None:
        self._q.put({"type": "progress", "stage": stage, "message": message})

    # --- Key generation lifecycle events ---

    def print_version_start(self) -> None:
        self._emit("start", "Starting article generation")

    def print_version_rag_search(self) -> None:
        self._emit("rag_search", "Searching the web for supporting context...")

    def print_version_context_query(self, queries: List[str]) -> None:
        self._emit("rag_queries", f"Search queries: {', '.join(queries)}")

    def print_version_ctx_details(self, ctx: str) -> None:
        import re
        urls = re.findall(r"\[.*?\]\((https?://[^\s)]+)\)", ctx)
        unique = len(set(urls))
        self._emit("rag_complete", f"Retrieved context from {unique} source(s) ({len(urls)} citations)")

    def print_version_generation(self) -> None:
        self._emit("generating", "Generating article...")

    def print_version_judging(self) -> None:
        self._emit("scoring", "Evaluating article quality...")

    def print_version_judgement(self, judgement) -> None:
        self._emit(
            "scored",
            f"Score: {judgement.percentage:.1f}% ({judgement.performance_tier}) — {judgement.word_count} words",
        )

    def print_version_context_reuse(self, recreate_ctx: bool) -> None:
        if recreate_ctx:
            self._emit("context", "Performing fresh web search for this iteration")
        else:
            self._emit("context", "Reusing initial search context")

    def print_version_message(self, message: str, emoji: str = "📝") -> None:
        self._emit("info", message)

    def print_iteration_start(self, iteration_n: int, max_iterations: int) -> None:
        self._emit("iteration_start", f"Iteration {iteration_n} of {max_iterations}")

    def print_job_complete(self, score: float, tier: str, word_count: int, target_achieved: bool) -> None:
        status = "Target achieved" if target_achieved else "Best effort result"
        self._emit("job_complete", f"Generation complete — {score:.1f}% ({tier}), {word_count} words — {status}")

    def print_version_complete(self, score: Optional[float] = None, success: bool = True) -> None:
        if success and score is not None:
            self._emit("complete_version", f"Version complete — score: {score:.1f}%")
        elif success:
            self._emit("complete_version", "Version complete")

    # --- Fact-checking events ---

    def print_fact_checking_start(self) -> None:
        self._emit("fact_checking", "Fact-checking the article against sources...")

    def print_fact_checking_results(self, fact_check_result) -> None:
        if fact_check_result:
            status = "passed" if fact_check_result.fact_check_passed else "needs revision"
            self._emit(
                "fact_check_results",
                f"Fact-check {status}: {fact_check_result.summary_feedback or ''}",
            )

    def print_fact_checking_passed(self) -> None:
        self._emit("fact_check_passed", "Fact-checking passed — article is ready")

    def print_fact_checking_failed(self, reason: str = "") -> None:
        self._emit("fact_check_failed", f"Fact-check issues found: {reason}" if reason else "Fact-check issues found")

    def print_humanizing_start(self) -> None:
        self._emit("humanizing", "Rewriting for natural voice...")

    def print_humanizing_complete(self) -> None:
        self._emit("humanized", "Humanization complete")

    def print_citation_issues(self, invalid_citations: int, uncited_claims: int) -> None:
        parts = []
        if invalid_citations:
            parts.append(f"{invalid_citations} invalid citation(s)")
        if uncited_claims:
            parts.append(f"{uncited_claims} uncited claim(s)")
        if parts:
            self._emit("citation_issues", "Issues: " + ", ".join(parts))

    # --- Suppress noisy verbose-only methods ---

    def print_section_header(self, *args, **kwargs) -> None:
        pass

    def print_generation_start(self, *args, **kwargs) -> None:
        self._emit("init", "Initialising generation pipeline...")

    def print_rag_status(self, *args, **kwargs) -> None:
        pass

    def print_generation_phase(self, phase: str, details: str = "") -> None:
        pass

    def print_final_summary(self, *args, **kwargs) -> None:
        pass

    def print_variable_dump(self, *args, **kwargs) -> None:
        pass

    def print_article_version_before_judging(self, *args, **kwargs) -> None:
        pass

    def print_judging_results_after_judging(self, *args, **kwargs) -> None:
        pass

    def print_score_report(self, *args, **kwargs) -> None:
        pass

    def print_version_exporting(self, *args, **kwargs) -> None:
        pass

    def print_export_success(self, *args, **kwargs) -> None:
        pass

    def print_export_failure(self, *args, **kwargs) -> None:
        pass

    def print_export_directory_created(self, *args, **kwargs) -> None:
        pass

    def print_export_directory_conflict(self, *args, **kwargs) -> None:
        pass


# ---------------------------------------------------------------------------
# Generation worker (runs in ThreadPoolExecutor thread)
# ---------------------------------------------------------------------------


def _run_generation(req: GenerateRequest, progress_queue: queue.Queue) -> None:
    """
    Blocking generation worker.  Runs in a ThreadPoolExecutor thread so it
    does not block the FastAPI event loop.

    Puts progress dicts into progress_queue throughout execution, and always
    ends with a "complete" or "error" event.
    """
    try:
        default = req.model
        logger.info(
            "Generation started — model=%s target=%.1f%% max_iter=%d words=%d-%d",
            default, req.target_score, req.max_iterations, req.word_count_min, req.word_count_max,
        )

        # Resolve (and cache) models for each component
        gen_cfg = resolve_model_cached(req.generator_model or default, default, temp=0.5)
        judge_cfg = resolve_model_cached(req.judge_model or default, default, temp=0.0)
        rag_cfg = resolve_model_cached(req.rag_model or default, default, temp=0.0)
        humanizer_cfg = resolve_model_cached(
            req.humanizer_model or req.generator_model or default, default, temp=0.7
        )
        models = {"generator": gen_cfg, "judge": judge_cfg, "rag": rag_cfg, "humanizer": humanizer_cfg}
        logger.info(
            "Models resolved — gen=%s  judge=%s  rag=%s  humanizer=%s",
            gen_cfg.name, judge_cfg.name, rag_cfg.name, humanizer_cfg.name,
        )

        om = QueueOutputManager(writer_id=1, progress_queue=progress_queue)

        # dspy.context is thread-local — safe for concurrent requests with
        # different models without disturbing the global dspy.configure() state.
        with dspy.context(lm=gen_cfg.dspy_lm):
            generator = LinkedInArticleGenerator(
                writer_id=1,
                target_score_percentage=req.target_score,
                max_iterations=req.max_iterations,
                word_count_min=req.word_count_min,
                word_count_max=req.word_count_max,
                models=models,
                verbose=False,
                recreate_ctx=req.recreate_ctx,
                auto=True,        # never prompt for user input
                export_dir=None,  # no filesystem writes from the API
                output_manager=om,
            )
            logger.info("Generator created — calling generate_article()")
            result = generator.generate_article(req.draft)
            logger.info("generate_article() returned")

        score = result["final_score"]
        logger.info(
            "Generation complete — score=%.1f%% tier=%s words=%d target_achieved=%s iterations=%d",
            score.percentage, score.performance_tier, score.word_count,
            result["target_achieved"], result["iterations_used"],
        )
        om.print_job_complete(
            score=score.percentage,
            tier=score.performance_tier,
            word_count=score.word_count,
            target_achieved=result["target_achieved"],
        )
        progress_queue.put({
            "type": "complete",
            "article": {
                "original": result["original_article"],
                "humanized": result["humanized_article"],
            },
            "score": {
                "percentage": score.percentage,
                "performance_tier": score.performance_tier,
                "word_count": score.word_count,
                "meets_requirements": score.meets_requirements,
                "overall_feedback": score.overall_feedback,
            },
            "target_achieved": result["target_achieved"],
            "iterations_used": result["iterations_used"],
        })

    except Exception as exc:
        logger.error("Generation failed: %s\n%s", exc, traceback.format_exc())
        progress_queue.put({"type": "error", "message": str(exc)})


# ---------------------------------------------------------------------------
# Application lifespan — configure DSPy once at startup
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    default_cfg = get_cached_model(API_DEFAULT_MODEL_NAME, temp=0.5)
    if default_cfg is None:
        raise RuntimeError(
            f"Cannot start API: default model '{API_DEFAULT_MODEL_NAME}' could not be resolved. "
            "Check GEMINI_API_KEY and model availability."
        )
    dspy.configure(lm=default_cfg.dspy_lm, async_max_workers=4)
    yield
    _executor.shutdown(wait=False)


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="LinkedIn Article Generator API",
    description=(
        "Generate world-class LinkedIn articles via a streaming SSE endpoint. "
        "Connect, receive real-time progress events, and get the finished article "
        "in the final 'complete' event."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
async def health():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.datetime.utcnow().isoformat()}


@app.post("/articles/generate", tags=["articles"])
async def generate_article(req: GenerateRequest):
    """
    Generate a LinkedIn article from a draft and stream progress via SSE.

    The response is a `text/event-stream`.  Each event is a JSON object with
    a `type` field:

    - `progress` — intermediate status update with `stage` and `message`
    - `heartbeat` — keep-alive ping (no payload)
    - `complete` — generation finished; contains `article` (with `original` and
      `humanized` keys), `score`, `target_achieved`, and `iterations_used`
    - `error` — generation failed; contains `message`

    The stream ends after the `complete` or `error` event.
    """
    progress_queue: queue.Queue = queue.Queue()
    loop = asyncio.get_event_loop()

    # Submit blocking generation to the thread pool
    future = loop.run_in_executor(_executor, _run_generation, req, progress_queue)

    async def event_stream() -> AsyncGenerator:
        while True:
            # Drain the queue without blocking the event loop
            try:
                event = await loop.run_in_executor(None, lambda: progress_queue.get(timeout=0.5))
                yield {"data": json.dumps(event)}
                if event.get("type") in ("complete", "error"):
                    break
            except queue.Empty:
                if future.done():
                    # Worker exited without sending a terminal event (shouldn't happen)
                    break
                # Send a heartbeat to keep the connection alive
                yield {"data": json.dumps({"type": "heartbeat"})}

    return EventSourceResponse(event_stream())
