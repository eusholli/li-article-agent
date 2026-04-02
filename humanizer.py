"""
Humanizer — AI-detection removal for LinkedIn articles.

Three-pass pipeline:
  Pass 1 (LLM ChainOfThought): Remove AI vocabulary patterns + apply Rakuten Symphony brand voice
  Pass 2 (Undetectable.ai humanizer API): Statistical transformation for detector evasion
  Pass 3 (LLM Predict, minimal): Restore brand voice constraints the API may have broken

Requires UNDETECTABLE_API_KEY in environment. If not set, Pass 2 is skipped gracefully —
Pass 1 + Pass 3 still run.
"""

import logging
import os
import time

import dspy
import httpx


class HumanizerRewriteSignature(dspy.Signature):
    """Rewrite the article to remove AI writing patterns and apply Rakuten Symphony brand voice.

    REMOVE THESE AI WRITING PATTERNS:

    1. AI vocabulary words — replace with plain alternatives:
       additionally→also/and, align with→match/fit, crucial→important/critical,
       delve→explore/look at, emphasizing→noting, enduring→lasting, enhance→improve,
       fostering→building, garner→get/earn, highlight (verb)→show/point to,
       interplay→interaction, intricate/intricacies→complex/complexity,
       key (adjective)→main/core, landscape (abstract)→field/sector/industry,
       pivotal→important/decisive, showcase→show/demonstrate, tapestry→mix/combination,
       testament→proof/sign, underscore→show/confirm, valuable→useful, vibrant→active

    2. Significance inflation — remove puffed-up importance statements:
       "serves as / stands as / marks / represents [a]" → use "is"/"are"
       "is a testament to", "underscores the importance of", "reflects broader",
       "symbolizing its enduring", "pivotal moment", "evolving landscape",
       "key turning point", "indelible mark" → cut entirely or rewrite factually

    3. Promotional language — replace with neutral factual description:
       boasts, breathtaking, groundbreaking (figurative), nestled, renowned,
       stunning, must-visit, vibrant, rich (figurative), commitment to → rewrite
       as plain statements with specific facts

    4. Superficial -ing phrases — cut the trailing elaboration:
       "..., highlighting [X]", "..., underscoring [Y]", "..., reflecting [Z]",
       "..., ensuring [A]", "..., showcasing [B]", "..., contributing to [C]" →
       make a separate sentence or cut entirely

    5. Negative parallelisms:
       "Not only X but Y", "It's not just about X, it's about Y" → rewrite directly

    6. Rule of three — break up forced triplets:
       If ideas are forced into groups of exactly three, split them or combine

    7. Em dash overuse — replace em dashes (—) with commas, periods, or conjunctions

    8. Boldface overuse — remove **bold** from phrases that are not truly critical terms

    9. Inline-header bullet lists — convert "- **Title:** Description" to prose or
       plain bullet lists without bolded lead-ins

    10. Vague attributions — remove or replace:
        "Experts argue", "Industry reports", "Observers have cited",
        "Some critics argue" → name a specific source or cut

    11. Generic positive conclusions — replace with specific plans or facts:
        "exciting times lie ahead", "the future looks bright",
        "this represents a major step in the right direction" → cut or rewrite

    12. Filler phrases — use the shorter form:
        "In order to" → "To"
        "Due to the fact that" → "Because"
        "At this point in time" → "Now"
        "It is important to note that" → cut the prefix
        "The system has the ability to" → "The system can"

    13. Formulaic challenges sections:
        "Despite challenges..., [subject] continues to thrive" → cut or rewrite
        with specific facts about what changed and why

    14. Excessive hedging — be direct:
        "could potentially possibly be argued that... might have some effect" →
        "may affect" or make a direct claim

    15. Copula avoidance — prefer "is"/"are":
        "serves as", "functions as", "stands as", "acts as" → "is"/"are"

    APPLY RAKUTEN SYMPHONY BRAND VOICE:
    - Tone: confident, professional, optimistic. Quiet boldness. No drama.
    - First-principles thinking: strip analogies, deconstruct complex systems,
      minimal text, clear logic. Write like an engineer explaining to a peer CTO.
    - Target audience: CTOs and VP Ops at tier-1 and tier-2 telcos.
    - FORBIDDEN WORDS (do not use under any circumstances):
      delve, tapestry, landscape, unlock, leverage, game-changer, overarching,
      paramount, "in conclusion", "it is important to note"
    - Never use three adjectives in a row.
    - Mix very short punchy sentences (1-4 words) with longer technical explanations.
    - Use PAS (Problem → Agitation → Solution) or AIDA structure.

    ADD PERSONALITY AND SOUL:
    - Vary sentence rhythm. Short punchy sentences. Then longer ones that take
      their time getting where they're going.
    - Have opinions — react to facts rather than neutrally reporting them.
    - Use specific details over vague claims.
    - Acknowledge complexity and mixed feelings where real.
    - Use "I" or direct address when it fits the LinkedIn format.
    """

    article: str = dspy.InputField(desc="The LinkedIn article to humanize")
    humanized_draft: str = dspy.OutputField(
        desc="The rewritten article with all AI patterns removed and brand voice applied. "
             "Must preserve all factual content, citations, and core arguments from the original."
    )


class BrandVoiceRestorationSignature(dspy.Signature):
    """Restore Rakuten Symphony brand voice constraints after humanization.

    ONLY fix these specific violations if present. Change nothing else.

    FORBIDDEN WORDS — replace with plain alternatives:
      delve, tapestry, landscape, unlock, leverage, game-changer, overarching,
      paramount, "in conclusion", "it is important to note"

    THREE ADJECTIVES — break any sequence of three or more consecutive adjectives.

    If no violations are present, return the text EXACTLY as received.
    No rephrasing. No restructuring. No improvements. Minimal diff only.
    """

    humanized_draft: str = dspy.InputField(
        desc="Article after Undetectable.ai processing"
    )
    final_article: str = dspy.OutputField(
        desc="Article with brand voice violations fixed. Minimal changes only — "
             "return text unchanged if no violations found."
    )


class UndetectableHumanizerApi:
    """Submit text to Undetectable.ai humanizer and poll for the result."""

    BASE_URL = "https://humanize.undetectable.ai"

    def __init__(self, api_key: str):
        self._headers = {"apikey": api_key}

    def humanize(
        self,
        text: str,
        progress_callback=None,
        timeout_seconds: int = 300,
    ) -> str:
        """Humanize text. Polls every 10s. Calls progress_callback(elapsed=N) each poll."""
        resp = httpx.post(
            f"{self.BASE_URL}/submit",
            headers=self._headers,
            timeout=30.0,
            json={
                "content": text,
                "readability": "University",
                "purpose": "Article",
                "strength": "More Human",
                "model": "v11",
            },
        )
        resp.raise_for_status()
        doc_id = resp.json()["id"]

        for i in range(timeout_seconds // 10):
            time.sleep(10)
            elapsed = (i + 1) * 10
            if progress_callback:
                progress_callback(elapsed=elapsed)
            doc = httpx.post(
                f"{self.BASE_URL}/document",
                headers=self._headers,
                json={"id": doc_id},
                timeout=30.0,
            ).json()
            if doc.get("status") == "done":
                return doc["output"]

        raise TimeoutError(
            f"Undetectable.ai humanizer timed out after {timeout_seconds}s for doc {doc_id}"
        )



class HumanizerModule(dspy.Module):
    """Three-pass humanizer: LLM brand voice → Undetectable.ai API → LLM brand voice restoration.

    Returns a dict:
        {"humanized_article": str}
    """

    def __init__(self, output_manager=None):
        super().__init__()
        self.rewrite = dspy.ChainOfThought(HumanizerRewriteSignature)
        self.restore = dspy.Predict(BrandVoiceRestorationSignature)
        self.output_manager = output_manager
        api_key = os.getenv("UNDETECTABLE_API_KEY")
        self.humanizer_api = UndetectableHumanizerApi(api_key) if api_key else None

    def forward(self, article: str) -> dict:
        """
        Humanize an article in three passes.

        Args:
            article: The article text to humanize.

        Returns:
            Dict with "humanized_article" (str).
        """
        # Pass 1: LLM — remove AI vocabulary + apply brand voice
        pass1 = self.rewrite(article=article)
        branded = pass1.humanized_draft

        # Pass 2: Undetectable.ai — statistical transformation
        if self.humanizer_api:
            if self.output_manager:
                self.output_manager.print_undetectable_submitted()
            try:
                api_output = self.humanizer_api.humanize(
                    branded,
                    progress_callback=(
                        self.output_manager.print_undetectable_progress
                        if self.output_manager
                        else None
                    ),
                )
                if self.output_manager:
                    self.output_manager.print_undetectable_complete()
            except Exception as e:
                logging.warning(f"Undetectable.ai humanizer skipped: {e}")
                api_output = branded
        else:
            api_output = branded

        # Pass 3: LLM — restore brand voice violations introduced by API
        pass3 = self.restore(humanized_draft=api_output)
        humanized = pass3.final_article

        return {"humanized_article": humanized}
