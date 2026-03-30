"""
Humanizer — Two-pass AI-detection removal for LinkedIn articles.

Pass 1 (HumanizerRewriteSignature): Remove the 25 AI writing patterns and
apply Rakuten Symphony brand voice.

Pass 2 (HumanizerCritiqueSignature): Self-critique remaining AI tells, then
produce the final rewrite.
"""

import dspy


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


class HumanizerCritiqueSignature(dspy.Signature):
    """Review the article for remaining signs of AI-generated writing, then produce a final rewrite.

    Step 1 — Ask yourself: "What makes the below so obviously AI generated?"
    Answer briefly: list the remaining tells as bullet points (specific phrases,
    patterns, structural habits, rhythm issues).

    Step 2 — Rewrite to fix every tell identified in Step 1.
    The final article must sound like a skilled human expert wrote it, not an AI assistant.
    Preserve all factual content, citations, and core arguments.
    """

    humanized_draft: str = dspy.InputField(
        desc="The article after the initial humanization pass"
    )
    remaining_tells: str = dspy.OutputField(
        desc="Brief bullet list of remaining AI tells found in the draft (e.g. '- Still uses pivotal', "
             "'- Paragraph 3 has three-item list pattern')"
    )
    final_article: str = dspy.OutputField(
        desc="The final rewritten article with all remaining AI tells eliminated. "
             "Same length and structure as the input — do not summarise or shorten."
    )


class HumanizerModule(dspy.Module):
    """Two-pass humanizer: rewrite then self-critique."""

    def __init__(self):
        super().__init__()
        self.rewrite = dspy.ChainOfThought(HumanizerRewriteSignature)
        self.critique = dspy.ChainOfThought(HumanizerCritiqueSignature)

    def forward(self, article: str) -> str:
        """
        Humanize an article in two passes.

        Args:
            article: The article text to humanize.

        Returns:
            The humanized article text.
        """
        pass1 = self.rewrite(article=article)
        pass2 = self.critique(humanized_draft=pass1.humanized_draft)
        return pass2.final_article
