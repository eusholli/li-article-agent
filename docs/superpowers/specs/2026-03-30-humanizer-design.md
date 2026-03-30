# Humanizer — Design Spec
**Date:** 2026-03-30
**Status:** Approved

## Problem

Generated LinkedIn articles score >80% on AI text detectors. The requirement is to reduce detection to <25% while preserving article quality (the 180-point score is not re-evaluated after humanization).

## Goal

Add a trusted, final post-processing step — a `HumanizerModule` — that rewrites the article to remove AI writing patterns and apply Rakuten Symphony brand voice. Same architecture pattern as fact-checking: runs once after the quality loop, no re-scoring.

---

## Approach

Two-pass humanizer using DSPy, inserted at the end of `generate_article_with_context()` before the return. Uses the generator model (creative writing capability required).

**Why two passes:** A single rewrite pass typically gets detection to 40-50%. The self-critique pass — "what still makes this obviously AI-generated?" — catches the tells that survive the first pass and pushes below 25%.

---

## Architecture

### New file: `humanizer.py`

Two DSPy signatures and one module.

**`HumanizerRewriteSignature`**
- Input: `article` (full article text)
- Output: `humanized_draft`
- Docstring embeds: all 25 humanizer anti-patterns (from `humanizer.md`) + Rakuten Symphony brand voice rules (from `symphony-brand-voice.md`): forbidden words, sentence rhythm (short punchy + long technical), PAS/AIDA structure, quiet boldness tone, no adjective triplets

**`HumanizerCritiqueSignature`**
- Input: `humanized_draft`
- Outputs: `remaining_tells` (brief bullets), `final_article` (post-critique rewrite)
- Docstring: "What makes this still obviously AI-generated? List the remaining tells briefly, then rewrite to fix them."

**`HumanizerModule(dspy.Module)`**
```python
class HumanizerModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.rewrite = dspy.ChainOfThought(HumanizerRewriteSignature)
        self.critique = dspy.ChainOfThought(HumanizerCritiqueSignature)

    def forward(self, article: str) -> str:
        pass1 = self.rewrite(article=article)
        pass2 = self.critique(humanized_draft=pass1.humanized_draft)
        return pass2.final_article
```

---

### Changes to `linkedin_article_generator.py`

**`__init__`** gains:
```python
humanizer_model: Optional[DspyModelConfig] = None
```

**`generate_article_with_context()`** — at the end, before `return final_result`:
```python
self.output_manager.print_humanizing_start()
humanizer_lm = (self.humanizer_model or self.generator_model).dspy_lm
with dspy.context(lm=humanizer_lm):
    humanizer = HumanizerModule()
    final_result["final_article"] = humanizer(final_result["final_article"])
self.output_manager.print_humanizing_complete()
```

`final_result["final_score"]` is left unchanged — reflects pre-humanization quality.

---

### Changes to `api_models.py`

One new optional field in `GenerateRequest`:
```python
humanizer_model: Optional[str] = Field(
    None,
    description="Model for humanization — defaults to generator_model if not set"
)
```

---

### Changes to `output_manager.py`

Two new lifecycle methods alongside the existing fact-check methods:
```python
def print_humanizing_start(self): ...
def print_humanizing_complete(self): ...
```

---

### Changes to `api.py`

**`QueueOutputManager`** — two new overrides:
```python
def print_humanizing_start(self):
    self._emit("humanizing", "Rewriting for natural voice...")

def print_humanizing_complete(self):
    self._emit("humanized", "Humanization complete")
```

**`_run_generation()`** — resolve humanizer model:
```python
humanizer_cfg = resolve_model_cached(
    req.humanizer_model or req.generator_model or default, default, temp=0.7
)
models = {"generator": gen_cfg, "judge": judge_cfg, "rag": rag_cfg, "humanizer": humanizer_cfg}
```

Temperature `0.7` for the humanizer — higher than judge (0.0) to encourage natural variation, lower than max to stay coherent.

---

## Data Flow

```
Draft
  → RAG retrieval
  → Generation loop (quality scoring, iterative improvement)
  → Fact-checking [existing trusted final step]
  → Humanization [new trusted final step]
      Pass 1: Remove 25 AI patterns + apply brand voice → humanized_draft
      Pass 2: Self-critique remaining tells → final_article
  → Return final_article to user
```

## Files Changed

| File | Change |
|------|--------|
| `humanizer.py` | New file — HumanizerRewriteSignature, HumanizerCritiqueSignature, HumanizerModule |
| `linkedin_article_generator.py` | Add humanizer_model param + call at end of generate_article_with_context() |
| `api_models.py` | Add optional humanizer_model field |
| `output_manager.py` | Add print_humanizing_start() and print_humanizing_complete() |
| `api.py` | Add QueueOutputManager overrides + resolve humanizer model in _run_generation() |

## Success Criteria

- AI text detection score <25% on the final returned article
- 180-point quality score unchanged (no re-scoring after humanization)
- Humanization adds ~2 LLM calls (~30-60s) latency to the pipeline
- Symphony brand voice constraints (forbidden words, sentence rhythm, PAS/AIDA) are applied
