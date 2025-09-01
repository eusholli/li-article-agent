# rag_fast.py
"""
Lean, fast web RAG retriever using Tavily + simple packing.
- Fully async
- No LLM calls during retrieval/cleaning
- Thread-safe module-level caching with atomic file operations
- Designed to hand a single, packed context string to your DSPy module
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
from tavily import AsyncTavilyClient  # pip install tavily-python
from dotenv import load_dotenv
import os
import logging
import dspy
from pydantic import BaseModel, Field
from typing import Dict
from dspy_factory import DspyModelConfig
from context_window_manager import ContextWindowManager
import re
from typing import Optional


logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

# -----------------------------------------------------------------------------
# Module-level cache with thread-safety
# -----------------------------------------------------------------------------

# Module-level cache and synchronization
_cache: Dict[str, Any] = {"searches": {}, "extractions": {}}
_cache_lock = asyncio.Lock()
_cache_initialized = False


def load_cache(cache_file: str) -> None:
    """Synchronously load cache from file."""
    global _cache_initialized, _cache
    if _cache_initialized:
        return  # Already loaded

    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
                _cache.update(loaded_data)
            logging.info(f"Loaded cache from {cache_file}")
    except Exception as e:
        logging.warning(f"Failed to load cache: {e}")
        _cache = {"searches": {}, "extractions": {}}  # Reset on error

    _cache_initialized = True


def save_cache(cache_file: str) -> None:
    """Synchronously save cache to file atomically."""
    try:
        # Write to temp file first
        temp_fd, temp_path = tempfile.mkstemp(
            suffix=".json", dir=os.path.dirname(cache_file)
        )
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(_cache, f, indent=2, ensure_ascii=False)
            # Atomic rename
            os.rename(temp_path, cache_file)
        except Exception:
            os.unlink(temp_path)
            raise
    except Exception as e:
        logging.warning(f"Failed to save cache: {e}")


async def get_cached_search(query: str) -> Optional[dict]:
    """Async wrapper for cache read."""
    async with _cache_lock:
        search_data = _cache["searches"].get(query)
        return search_data.get("response") if search_data else None


async def set_cached_search(query: str, response: dict, cache_file: str) -> None:
    """Async wrapper for cache write."""
    async with _cache_lock:
        _cache["searches"][query] = {"timestamp": time.time(), "response": response}
        # Run sync save in thread pool to avoid blocking event loop
        await asyncio.to_thread(save_cache, cache_file)


async def get_cached_extraction(url: str) -> Optional[dict]:
    """Async wrapper for extraction cache read."""
    async with _cache_lock:
        return _cache["extractions"].get(url)


async def set_cached_extraction(url: str, data: dict, cache_file: str) -> None:
    """Async wrapper for extraction cache write."""
    async with _cache_lock:
        _cache["extractions"][url] = data
        await asyncio.to_thread(save_cache, cache_file)


def check_cached_urls(urls: List[str]) -> Tuple[List[str], List[str]]:
    """
    Check which URLs are in the cache and which need to be fetched.

    This function checks the current in-memory cache state.
    The cache is loaded once when the first TavilyWebRetriever instance is created.

    Args:
        urls: List of URL strings to check

    Returns:
        Tuple of (cached_urls, urls_to_fetch)
        - cached_urls: List of URLs that are already cached
        - urls_to_fetch: List of URLs that need to be fetched from the API
    """
    # Note: This function is synchronous and checks the current in-memory cache.
    # Cache loading is handled in TavilyWebRetriever.__init__() to ensure
    # the latest persisted cache is loaded before any operations.
    cached_urls = []
    urls_to_fetch = []

    for url in urls:
        if url in _cache["extractions"]:
            cached_urls.append(url)
        else:
            urls_to_fetch.append(url)

    return cached_urls, urls_to_fetch


# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------


def _unique_stable(seq: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for s in seq:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


# -----------------------------------------------------------------------------
# Async Tavily search + extract
# -----------------------------------------------------------------------------


@dataclass
class TavilySettings:
    api_key: str | None = None
    search_depth: str = "advanced"  # "basic" or "advanced"
    max_results: int = 6  # total results per query (0..20)
    chunks_per_source: int = 2  # relevant snippets per result (advanced only)
    include_raw_content: str | bool = "text"  # "markdown" | "text" | False
    timeout: int = 45
    extract_format: str = "markdown"  # "markdown" | "text"
    extract_depth: str = "basic"  # "basic" | "advanced"
    concurrent_requests: int = 8  # client-side concurrency
    cache_file: str = "tavily_cache.json"  # persistent cache file


class TopicExtractionResult(BaseModel):
    """Result structure for topic extraction focused on analytical thinking evaluation."""

    main_topic: str = Field(
        ...,
        description="Main topic/subject of the article for web search",
    )
    search_query: List[str] = Field(
        ...,
        description="A list of at most 3 optimized search queries to find evidence of fundamental analysis, root cause examination, and deep thinking patterns that help evaluate if the article breaks down complex problems into basic components rather than relying on analogies or surface-level solutions",
    )
    needs_research: bool = Field(
        ...,
        description="Boolean: whether this topic would benefit from web research context to evaluate analytical depth",
    )


class TopicExtractionSignature(dspy.Signature):
    """Extract the main topic and generate search queries to evaluate if the article demonstrates deep analytical thinking."""

    draft_or_outline = dspy.InputField(
        desc="Article draft or outline to analyze for main topic and analytical approach"
    )

    output: TopicExtractionResult = dspy.OutputField(
        desc="Extracted main topic, search queries optimized to find evidence of fundamental analysis vs surface-level thinking, and research needs flag"
    )


class TavilyWebRetriever:
    """
    High-throughput retriever that:
      1) runs Tavily searches for each query
      2) extracts raw content for each result URL
      3) returns (passages, urls) with basic dedup and quality guards

    Thread-safety: Uses module-level cache with asyncio.Lock for concurrent access.
    All instances share the same cache and file, ensuring consistency across multiple retrievers.
    """

    def __init__(self, settings: TavilySettings | None = None):
        self.settings = settings or TavilySettings(api_key=os.getenv("TAVILY_API_KEY"))
        if AsyncTavilyClient is None:
            raise RuntimeError("tavily-python not installed. pip install tavily-python")
        if not self.settings.api_key:
            raise RuntimeError("TAVILY_API_KEY is not set.")

        self.client = AsyncTavilyClient(self.settings.api_key)
        self._sem = asyncio.Semaphore(self.settings.concurrent_requests)

        # Load cache once at module level
        load_cache(self.settings.cache_file)

    async def _asearch(self, query: str) -> dict:
        # Check cache first
        cached = await get_cached_search(query)
        if cached:
            logging.info(f"Cache hit for search query: {query}")
            return cached

        # Cache miss - make API call
        async with self._sem:
            response = await self.client.search(
                query=query,
                search_depth=self.settings.search_depth,
                max_results=self.settings.max_results,
                chunks_per_source=(
                    self.settings.chunks_per_source
                    if self.settings.search_depth == "advanced"
                    else None
                ),
                include_raw_content=self.settings.include_raw_content,
                timeout=self.settings.timeout,
            )

        # Update cache
        await set_cached_search(query, response, self.settings.cache_file)
        logging.info(f"Cached search result for query: {query}")

        return response

    async def _aextract(self, urls: List[str]) -> dict:
        async with _cache_lock:
            cached_results = []
            urls_to_fetch = []

            for url in urls[:20]:  # Respect Tavily's 20 URL limit
                cached = _cache["extractions"].get(url)
                if cached:
                    logging.info(f"Cache hit for extraction URL: {url}")
                    cached_results.append(cached)
                else:
                    urls_to_fetch.append(url)

        # Make API call only for uncached URLs
        if urls_to_fetch:
            async with self._sem:
                response = await self.client.extract(
                    urls=urls_to_fetch,
                    format=self.settings.extract_format,
                    extract_depth=self.settings.extract_depth,
                    timeout=self.settings.timeout,
                )

            # Update cache
            async with _cache_lock:
                if "results" in response:
                    for item in response["results"]:
                        url = item.get("url")
                        if url:
                            data = {
                                "timestamp": time.time(),
                                "raw_content": item.get("raw_content", ""),
                                "url": url,
                            }
                            _cache["extractions"][url] = data
                            logging.info(f"Cached extraction result for URL: {url}")
                await asyncio.to_thread(save_cache, self.settings.cache_file)

            all_results = cached_results + response.get("results", [])
        else:
            # All results were cached
            all_results = cached_results

        return {"results": all_results}

    async def search_and_extract(
        self, queries: List[str]
    ) -> Tuple[List[str], List[str]]:
        # 1) search all queries concurrently
        search_responses = await asyncio.gather(
            *[self._asearch(q) for q in queries], return_exceptions=True
        )

        urls: List[str] = []
        for r in search_responses:
            if isinstance(r, Exception):
                continue
            for item in r.get("results", []):
                url = item.get("url")
                if url:
                    urls.append(url)

        urls = _unique_stable(urls)
        if not urls:
            return [], []

        # 2) extract in small batches to minimize latency
        batches = [urls[i : i + 20] for i in range(0, len(urls), 20)]
        extract_responses = await asyncio.gather(
            *[self._aextract(b) for b in batches], return_exceptions=True
        )

        passages: List[str] = []
        ordered_urls: List[str] = []
        for resp in extract_responses:
            if isinstance(resp, Exception):
                continue
            for item in resp.get("results", []):
                url = item.get("url")
                raw = item.get("raw_content") or ""
                if url and raw and len(raw) > 200:  # guard against tiny pages
                    passages.append(raw)
                    ordered_urls.append(url)

        return passages, ordered_urls


# -----------------------------------------------------------------------------
# Minimal non-LLM cleaner + packer
# -----------------------------------------------------------------------------

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_WS = re.compile(r"\s+")


def _strip_boilerplate(text: str) -> str:
    # aggressive but safe: drop nav/footers and very short lines
    lines = [l.strip() for l in text.splitlines()]
    keep: List[str] = []
    for ln in lines:
        if not ln:
            continue
        low = ln.lower()
        if any(
            x in low for x in ("subscribe", "cookie", "privacy policy", "terms of use")
        ):
            continue
        if ln.startswith(("©", "Copyright", "All rights reserved")):
            continue
        if len(ln) < 40 and not re.search(r"\d", ln):
            # Drop ultra-short lines without numbers
            continue
        keep.append(ln)
    return "\n".join(keep)


def _salient_sentences(text: str) -> List[str]:
    text = _WS.sub(" ", text).strip()
    if not text:
        return []
    sents = _SENT_SPLIT.split(text)
    salient: List[str] = []
    for s in sents:
        s = s.strip()
        if len(s) < 40:
            continue
        # prefer sentences with facts: numbers, units, dates, %, $, proper nouns
        if re.search(r"(\d{2,4}|\d+[%$])", s) or re.search(r"\b(20\d{2}|19\d{2})\b", s):
            salient.append(s)
        elif len(s) > 120:
            salient.append(s)
    return salient if salient else sents[:5]  # fallback


def dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in items:
        k = re.sub(r"\W+", "", x.lower())
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


# Tokenizer: default to cl100k_base if tiktoken exists, otherwise naive char budget.
try:
    import tiktoken

    def _get_encoding(model: Optional[str]) -> tiktoken.Encoding:
        if model:
            try:
                return tiktoken.encoding_for_model(model)
            except Exception:
                pass
        return tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str, model: Optional[str] = None) -> int:
        enc = _get_encoding(model)
        return len(enc.encode(text))

except Exception:  # pragma: no cover

    def count_tokens(text: str, model: Optional[str] = None) -> int:
        # ~4 chars per token heuristic
        return max(1, len(text) // 4)


@dataclass
class PackSettings:
    target_model: str | None = (
        None  # e.g. "gpt-4o-mini" (optional, for more accurate tokenization)
    )
    max_input_tokens: int = 100_000  # caller-provided budget for the LM input
    reserve_for_prompt_and_answer: int = 2_000  # headroom
    max_per_doc_tokens: int = 6_000  # soft cap per source


class TextPacker:
    def __init__(self, settings: PackSettings | None = None):
        self.settings = settings or PackSettings()

    def pack(self, passages: List[str], urls: List[str]) -> Tuple[str, List[str]]:
        """
        Returns a single context string (with URL markers) and the list of URLs actually packed.
        Strategy:
          - strip boilerplate
          - pick salient sentences
          - dedupe aggressively
          - greedily pack under the token budget
        """
        assert len(passages) == len(urls), "passages and urls must align"

        budget = max(
            1,
            self.settings.max_input_tokens
            - self.settings.reserve_for_prompt_and_answer,
        )
        chosen_urls: List[str] = []

        # Precompute cleaned & salient text per doc
        docs: List[Tuple[str, str]] = []  # (url, compressed_text)
        for url, raw in zip(urls, passages):
            cleaned = _strip_boilerplate(raw)
            sents = _salient_sentences(cleaned)
            sents = dedupe_keep_order(sents)
            # Soft per-doc cap to avoid one giant page eating the budget
            running: List[str] = []
            for s in sents:
                if (
                    count_tokens(" ".join(running + [s]), self.settings.target_model)
                    > self.settings.max_per_doc_tokens
                ):
                    break
                running.append(s)
            if running:
                docs.append((url, " ".join(running)))

        # Greedy pack
        chunks: List[str] = []
        total = 0
        for url, body in docs:
            header = f"[SOURCE] {url}\n"
            candidate = header + body + "\n\n"
            c_tokens = count_tokens(candidate, self.settings.target_model)
            if total + c_tokens > budget:
                # try half of it
                half = body[: max(200, len(body) // 2)]
                candidate = header + half + "\n\n"
                c_tokens = count_tokens(candidate, self.settings.target_model)
                if total + c_tokens > budget:
                    break
            chunks.append(candidate)
            chosen_urls.append(url)
            total += c_tokens

        return "".join(chunks), chosen_urls


# -----------------------------------------------------------------------------
# Example end-to-end helper
# -----------------------------------------------------------------------------


async def retrieve_and_pack(
    draft_article: str,
    models: Dict[str, DspyModelConfig],
    k: int = 6,
) -> Tuple[str, List[str]]:

    # Use centralized context window management for intelligent sizing
    try:
        # Use centralized context manager for RAG limit calculation
        context_manager = ContextWindowManager(models["generator"])
        max_total_chars = context_manager.get_rag_limit()
        max_rag_tokens = context_manager.chars_to_tokens(max_total_chars)
        max_rag_tokens_per_doc = max_rag_tokens // k
        print(
            f"🧠 Using centralized RAG limit: {max_total_chars:,} chars (35% allocation)"
        )
    except Exception as e:
        logging.warning(
            f"Could not determine context window from manager, using default: {e}"
        )
        max_rag_tokens = 100000

    topic_extractor = dspy.ChainOfThought(TopicExtractionSignature)

    # Use generator LLM because temperature is not zero
    with dspy.context(models=models["generator"].dspy_lm):
        topic_results = topic_extractor(draft_or_outline=draft_article).output

    if topic_results.needs_research:
        queries = topic_results.search_query
        print(f"Main topic identified: {topic_results.main_topic}")
        print(f"🔍 Extracted search queries: {queries}")
        queries = [
            topic_results.main_topic
        ] + queries  # Always include main topic at the front
    else:
        print("No research needed based on topic extraction.")
        return "", []

    tavily = TavilySettings(
        max_results=k,
        chunks_per_source=2,
        include_raw_content="text",
        api_key=os.getenv("TAVILY_API_KEY"),
    )

    model_name = models["generator"].name if models["generator"] else "unknown"
    pack = PackSettings(
        target_model=model_name,
        max_input_tokens=max_rag_tokens,
        reserve_for_prompt_and_answer=0,
        max_per_doc_tokens=max_rag_tokens_per_doc,
    )

    retriever = TavilyWebRetriever(tavily)
    passages, urls = await retriever.search_and_extract(queries)
    if not passages:
        return "", []
    context, used_urls = TextPacker(pack).pack(passages, urls)
    return context, used_urls
