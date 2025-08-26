# html_text_cleaner_fast.py
"""
Drop-in replacement for a simpler, faster cleaner/packer.
Keeps the public API: clean_and_limit_passages(passages, urls) -> (passages, urls)
But removes *all* LLM calls and relies on deterministic heuristics + token budget.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Optional

# Reuse the packing primitives from rag_fast to avoid duplication if present.
try:
    from rag_fast import TextPacker, PackSettings, _strip_boilerplate, _salient_sentences, dedupe_keep_order, count_tokens  # type: ignore
except Exception:
    # Minimal inline fallbacks
    import re
    _SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
    _WS = re.compile(r"\s+")
    def _strip_boilerplate(text: str) -> str:
        lines = [l.strip() for l in text.splitlines()]
        keep = []
        for ln in lines:
            if not ln: 
                continue
            low = ln.lower()
            if any(x in low for x in ("subscribe", "cookie", "privacy policy", "terms of use")):
                continue
            if ln.startswith(("©", "Copyright", "All rights reserved")):
                continue
            if len(ln) < 40 and not re.search(r"\d", ln):
                continue
            keep.append(ln)
        return "\n".join(keep)

    def _salient_sentences(text: str):
        text = _WS.sub(" ", text).strip()
        if not text:
            return []
        sents = _SENT_SPLIT.split(text)
        salient = []
        for s in sents:
            s = s.strip()
            if len(s) < 40:
                continue
            if re.search(r"(\d{2,4}|\d+[%$])", s) or re.search(r"\b(20\d{2}|19\d{2})\b", s):
                salient.append(s)
            elif len(s) > 120:
                salient.append(s)
        return salient if salient else sents[:5]

    def dedupe_keep_order(items: List[str]) -> List[str]:
        seen = set(); out = []
        for x in items:
            k = re.sub(r"\W+", "", x.lower())
            if k not in seen:
                seen.add(k)
                out.append(x)
        return out

    try:
        import tiktoken
        def count_tokens(text: str, model: Optional[str]=None) -> int:
            try:
                enc = tiktoken.encoding_for_model(model) if model else tiktoken.get_encoding("cl100k_base")
            except Exception:
                enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
    except Exception:
        def count_tokens(text: str, model: Optional[str]=None) -> int:
            return max(1, len(text)//4)

@dataclass
class CleanerSettings:
    # Keep a single source of truth for budgets
    target_model: Optional[str] = None
    max_input_tokens: int = 100_000
    reserve_for_prompt_and_answer: int = 2_000
    max_per_doc_tokens: int = 6_000

class HTMLTextCleaner:
    """
    Very small, robust cleaner that:
      - strips boilerplate
      - keeps salient sentences
      - dedupes lines
      - greedily fits under a single token budget
    """

    def __init__(self, settings: CleanerSettings | None = None):
        self.settings = settings or CleanerSettings()

    def clean_and_limit_passages(self, passages: List[str], urls: List[str]) -> Tuple[List[str], List[str]]:
        if not passages or not urls or len(passages) != len(urls):
            return [], []

        # Pre-clean & compress each passage
        compressed: List[str] = []
        for raw in passages:
            text = _strip_boilerplate(raw)
            sents = _salient_sentences(text)
            sents = dedupe_keep_order(sents)
            # soft cap per document
            buf: List[str] = []
            for s in sents:
                if count_tokens(" ".join(buf + [s]), self.settings.target_model) > self.settings.max_per_doc_tokens:
                    break
                buf.append(s)
            compressed.append(" ".join(buf) if buf else "")

        # Greedy pack across docs under the global budget
        budget = max(1, self.settings.max_input_tokens - self.settings.reserve_for_prompt_and_answer)
        out_passages: List[str] = []
        out_urls: List[str] = []
        used = 0

        for u, doc in zip(urls, compressed):
            if not doc:
                continue
            add = doc
            add_tokens = count_tokens(add, self.settings.target_model)
            if used + add_tokens > budget:
                # try half
                half = add[: max(200, len(add)//2)]
                add_tokens = count_tokens(half, self.settings.target_model)
                if used + add_tokens > budget:
                    break
                add = half
            out_passages.append(add)
            out_urls.append(u)
            used += add_tokens

        return out_passages, out_urls
