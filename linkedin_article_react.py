#!/usr/bin/env python3
"""
LinkedIn Article REACT Module

This module implements a DSPy REACT (Reasoning + Acting) approach that orchestrates:
- Topic extraction and analysis
- RAG web search for context
- Article generation with context
- Iterative scoring and improvement

The REACT module uses simple if/then reasoning to determine when to search for context
and how to integrate it into the article generation process.
"""

import dspy
from typing import Dict, Any, List, Optional
import logging

from linkedin_article_generator import LinkedInArticleGenerator
from rag import TavilyRAGModule

# Configure logging - suppress verbose LiteLLM output
logging.basicConfig(level=logging.WARNING)  # Only show warnings and errors
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Keep INFO level for this module only

# Suppress LiteLLM verbose logging
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("litellm").setLevel(logging.WARNING)


class TopicExtractionSignature(dspy.Signature):
    """Extract the main topic for web search from article draft or outline."""

    draft_or_outline = dspy.InputField(
        desc="Article draft or outline to analyze for main topic"
    )

    main_topic = dspy.OutputField(
        desc="Main topic/subject of the article for web search"
    )
    search_query = dspy.OutputField(
        desc="Optimized search query to find relevant context for the topic"
    )
    needs_research = dspy.OutputField(
        desc="Boolean: whether this topic would benefit from web research context"
    )


class LinkedInArticleREACT(dspy.Module):
    """
    REACT (Reasoning + Acting) module for LinkedIn article generation.

    This module implements a simple reasoning workflow:
    1. Reason: Extract main topic and determine if research is needed
    2. Act: Search web for relevant context if needed
    3. Act: Generate article with context using enhanced LinkedInArticleGenerator
    4. Return: Complete article generation results with REACT metadata

    The reasoning is kept simple with if/then logic as requested.
    """

    def __init__(
        self,
        target_score_percentage: float = 89.0,
        max_iterations: int = 10,
        word_count_min: int = 2000,
        word_count_max: int = 2500,
        rag_k: int = 5,
    ):
        """
        Initialize the REACT module.

        Args:
            target_score_percentage: Target score percentage for world-class articles
            max_iterations: Maximum number of improvement iterations
            word_count_min: Minimum target word count
            word_count_max: Maximum target word count
            rag_k: Number of search results to retrieve for context
        """
        super().__init__()

        # Initialize components
        self.topic_extractor = dspy.ChainOfThought(TopicExtractionSignature)
        self.article_generator = LinkedInArticleGenerator(
            target_score_percentage, max_iterations, word_count_min, word_count_max
        )

        # Configure RAG system
        try:
            self.rag_module = TavilyRAGModule(k=rag_k, include_raw_content=True)
            self.rag_available = True
            logger.info(f"RAG system configured successfully with k={rag_k}")
        except Exception as e:
            logger.warning(f"RAG system not available: {e}")
            self.rag_available = False

        self.rag_k = rag_k

    def forward(self, draft_or_outline: str, verbose: bool = True) -> Dict[str, Any]:
        """
        REACT workflow for article generation.

        Args:
            draft_or_outline: Initial draft article or outline
            verbose: Whether to print progress updates

        Returns:
            Dict containing final article, score, generation metadata, and REACT metadata
        """
        if verbose:
            print("🧠 REACT: Starting intelligent article generation workflow")
            print("=" * 60)

        # Step 1: REASON - Extract main topic and determine research needs
        topic_analysis = self._reason_about_topic(draft_or_outline, verbose)

        # Step 2: ACT - Search for context if needed and available
        context = self._act_search_context(topic_analysis, verbose)

        # Step 3: ACT - Generate article with context
        result = self._act_generate_article(draft_or_outline, context, verbose)

        # Add REACT metadata to results
        result["react_metadata"] = {
            "main_topic": topic_analysis.get("main_topic", ""),
            "search_query": topic_analysis.get("search_query", ""),
            "needs_research": topic_analysis.get("needs_research", False),
            "research_performed": bool(context.strip()),
            "context_length": len(context),
            "rag_available": self.rag_available,
            "reasoning_steps": [
                "Analyzed topic for research needs",
                "Searched for context" if context else "Skipped search",
                (
                    "Generated article with context"
                    if context
                    else "Generated article without context"
                ),
            ],
        }

        if verbose:
            self._print_react_summary(result["react_metadata"])

        return result

    def _reason_about_topic(
        self, draft_or_outline: str, verbose: bool
    ) -> Dict[str, Any]:
        """
        REASON: Analyze the topic to determine research needs.

        Simple reasoning logic:
        - Extract main topic from draft
        - Determine if topic would benefit from web research
        - Generate optimized search query if research is needed
        """
        if verbose:
            print("🧠 REACT REASONING: Analyzing topic for research needs...")

        try:
            # Extract topic and determine research needs
            result = self.topic_extractor(draft_or_outline=draft_or_outline)

            topic_analysis = {
                "main_topic": result.main_topic,
                "search_query": result.search_query,
                "needs_research": self._parse_boolean(result.needs_research),
            }

            if verbose:
                print(f"📝 Main topic identified: {topic_analysis['main_topic']}")
                print(f"🔍 Research needed: {topic_analysis['needs_research']}")
                if topic_analysis["needs_research"]:
                    print(f"🔍 Search query: {topic_analysis['search_query']}")

            return topic_analysis

        except Exception as e:
            logger.error(f"Error in topic analysis: {e}")
            if verbose:
                print(f"⚠️ Topic analysis failed, proceeding without research")

            # Fallback: no research
            return {
                "main_topic": "Unknown topic",
                "search_query": "",
                "needs_research": False,
            }

    def _act_search_context(self, topic_analysis: Dict[str, Any], verbose: bool) -> str:
        """
        ACT: Search for web context if research is needed and RAG is available.

        Simple action logic:
        - If research not needed: return empty context
        - If RAG not available: return empty context
        - If research needed and RAG available: perform search
        """
        # Simple if/then reasoning for search decision
        if not topic_analysis.get("needs_research", False):
            if verbose:
                print(
                    "🧠 REACT DECISION: No research needed, proceeding without context"
                )
            return ""

        if not self.rag_available:
            if verbose:
                print("⚠️ REACT DECISION: Research needed but RAG not available")
            return ""

        # Perform web search
        if verbose:
            print("🌐 REACT ACTION: Searching for topic context...")

        try:
            search_query = topic_analysis.get("search_query", "")
            if not search_query:
                if verbose:
                    print("⚠️ No search query available, skipping search")
                return ""

            # Use TavilyRAGModule to search and get structured markdown context
            rag_result = self.rag_module.forward(search_query)

            # Extract the markdown answer from the RAG result
            context = (
                rag_result.markdown_answer
                if hasattr(rag_result, "markdown_answer")
                else ""
            )

            if verbose:
                context_length = len(context)
                if context_length > 0:
                    print(f"✅ Retrieved RAG context: {context_length} characters")
                    # Show a preview of the context
                    preview = context[:200] + "..." if len(context) > 200 else context
                    print(f"📄 Context preview: {preview}")
                else:
                    print("⚠️ No context retrieved from search")

            return context

        except Exception as e:
            logger.error(f"Error in web search: {e}")
            if verbose:
                print(f"⚠️ Web search failed: {e}")
            return ""

    def _act_generate_article(
        self, draft_or_outline: str, context: str, verbose: bool
    ) -> Dict[str, Any]:
        """
        ACT: Generate article using enhanced LinkedInArticleGenerator with context.
        """
        if verbose:
            print("📝 REACT ACTION: Generating article with enhanced context...")

        # Use the enhanced article generator with context
        result = self.article_generator.generate_article_with_context(
            draft_or_outline, context, verbose
        )

        return result

    def _parse_boolean(self, value: Any) -> bool:
        """
        Parse various boolean representations from LLM output.

        Args:
            value: Value to parse as boolean

        Returns:
            bool: Parsed boolean value
        """
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            value_lower = value.lower().strip()
            return value_lower in ["true", "yes", "1", "needed", "required"]

        return bool(value)

    def _print_react_summary(self, react_metadata: Dict[str, Any]):
        """Print a summary of the REACT workflow execution."""
        print("\n" + "=" * 60)
        print("🧠 REACT WORKFLOW SUMMARY")
        print("=" * 60)

        print(f"📝 Main Topic: {react_metadata['main_topic']}")
        print(f"🔍 Research Needed: {react_metadata['needs_research']}")
        print(f"🌐 Research Performed: {react_metadata['research_performed']}")

        if react_metadata["research_performed"]:
            print(f"📄 Context Length: {react_metadata['context_length']} characters")
            print(f"🔍 Search Query: {react_metadata['search_query']}")

        print("\n📋 REASONING STEPS:")
        for i, step in enumerate(react_metadata["reasoning_steps"], 1):
            print(f"  {i}. {step}")

        print("\n✅ REACT workflow completed successfully!")

    # Convenience methods for compatibility
    def generate_article(
        self, draft_or_outline: str, verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Generate article using REACT workflow.

        This method provides the same interface as LinkedInArticleGenerator
        for easy drop-in replacement.
        """
        return self.forward(draft_or_outline, verbose)

    def export_results(self, filepath: str):
        """
        Export generation results to JSON file.

        This method delegates to the underlying LinkedInArticleGenerator
        for compatibility with the main.py interface.
        """
        if hasattr(self.article_generator, "export_results"):
            return self.article_generator.export_results(filepath)
        else:
            # Fallback: create basic export data
            import json

            export_data = {
                "message": "REACT generation completed",
                "rag_available": self.rag_available,
                "versions": (
                    len(self.article_generator.versions)
                    if hasattr(self.article_generator, "versions")
                    else 0
                ),
                "final_article": "Export not available - use generate_article() first",
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    # Test the REACT module
    react_generator = LinkedInArticleREACT()

    sample_draft = """
    # The Future of Remote Work in 2025
    
    Remote work has fundamentally changed how we think about productivity and collaboration.
    
    Key trends:
    - Hybrid work models becoming standard
    - AI tools enhancing remote collaboration
    - New challenges in team management
    - Impact on company culture
    
    The future will likely be more flexible than ever before.
    """

    print("Testing LinkedIn Article REACT Module with sample draft...")
    result = react_generator.generate_article(sample_draft, verbose=True)

    print(f"\nREACT generation completed.")
    print(f"Final article length: {len(result['final_article'])} characters")
    print(f"REACT metadata: {result.get('react_metadata', {})}")
