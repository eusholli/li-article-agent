"""
RAG (Retrieval-Augmented Generation) Module for LinkedIn Article Generator

This module implements DSPy-based RAG search functionality that can retrieve
relevant information from web sources to enhance article generation.

Based on the implementation guide in rag-implementation.md, this module provides:
- TavilyRetriever: Custom DSPy retriever using DuckDuckGo search
- RAGModule: Complete RAG pipeline for question answering
- search_and_retrieve: Simple function interface for k max results
"""

import dspy
import os
from ddgs import DDGS
from typing import Dict, List, Union, Optional
import logging
from tavily import TavilyClient
import asyncio
from tavily import AsyncTavilyClient
from dotenv import load_dotenv
import dspy
from tavily import TavilyClient
from typing import List, Union
from dspy import Prediction
from html_text_cleaner import HTMLTextCleaner
from dspy_factory import DspyModelConfig
from context_window_manager import ContextWindowManager
from pydantic import BaseModel, Field


# Load environment variables from .env file
load_dotenv()

# Configure logging - suppress verbose LiteLLM output
logging.basicConfig(level=logging.WARNING)  # Only show warnings and errors
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Keep INFO level for this module only

# Suppress LiteLLM verbose logging
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("litellm").setLevel(logging.WARNING)


class TopicExtractionResult(BaseModel):
    """Result structure for topic extraction."""

    main_topic: str = Field(
        ...,
        description="Main topic/subject of the article for web search",
    )
    search_query: List[str] = Field(
        ...,
        description="A list of at most 3 optimized search queries to find relevant context for the topic",
    )
    needs_research: bool = Field(
        ...,
        description="Boolean: whether this topic would benefit from web research context",
    )


class TopicExtractionSignature(dspy.Signature):
    """Extract the main topic for web search from article draft or outline."""

    draft_or_outline = dspy.InputField(
        desc="Article draft or outline to analyze for main topic"
    )

    output: TopicExtractionResult = dspy.OutputField(
        desc="Extracted main topic, search queries, and research needs flag"
    )


class TavilyRetriever(dspy.Retrieve):

    def __init__(self, models: Dict[str, DspyModelConfig], k=3, max_total_chars=None):
        """
        Initialize the Tavily Retriever.

        Args:
            k: Number of results to retrieve
            max_total_chars: Maximum total characters across all passages
            model_name: Optional model name for RAG components (for consistency with other components)
        """
        super().__init__(k=k)
        self.tavily = AsyncTavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        self.models = models  # Store for potential future use
        self.topic_extractor = dspy.ChainOfThought(TopicExtractionSignature)

        # Use centralized context window management for intelligent sizing
        if max_total_chars is None:
            try:
                # Use centralized context manager for RAG limit calculation
                context_manager = ContextWindowManager(models["generator"])
                max_total_chars = context_manager.get_rag_limit()
                print(
                    f"🧠 Using centralized RAG limit: {max_total_chars:,} chars (35% allocation)"
                )
            except Exception as e:
                logger.warning(
                    f"Could not determine context window from manager, using default: {e}"
                )
                max_total_chars = 100000

        self.max_total_chars = max_total_chars
        self.text_cleaner = HTMLTextCleaner(
            models=models, max_total_chars=max_total_chars
        )
        # dspy.settings.configure(rm=self)

    async def fetch_and_extract(self, query: List[str], k: int):

        k = k if k is not None else self.k
        queries = [query] if isinstance(query, str) else query

        # Perform the search queries concurrently, passing the entire query dictionary
        responses = await asyncio.gather(
            *[
                self.tavily.search(query=q, search_depth="advanced", max_results=k)
                for q in queries
            ]
        )

        # Filter URLs with a score greater than 0.5. Alternatively, you can use a re-ranking model or an LLM to identify the most relevant sources, or cluster your documents and extract content only from the most relevant cluster

        print(f"RAG responses for query '{query}':")
        relevant_urls = []
        for response in responses:
            for result in response.get("results", []):
                print(f"- {result.get('url', '')[:200]}...")

                if result.get("score", 0) > 0.5:
                    relevant_urls.append(result.get("url"))

        # Extract content from the relevant URLs
        extracted_data = await asyncio.gather(
            *(self.tavily.extract(url) for url in relevant_urls)
        )

        # Collect raw passages and URLs
        raw_passages = []
        raw_urls = []

        print(f"RAG results for {queries}:")
        for data in extracted_data:
            results = data.get("results", [])
            if results:
                for result in results:
                    raw_content = result.get("raw_content", "")
                    url = result.get("url", "")

                    if raw_content and url:  # Only add if both content and URL exist
                        raw_passages.append(raw_content)
                        raw_urls.append(url)
                        print(f"- {url[:100]}... {len(raw_content)} chars")

        print(f"📥 Collected {len(raw_passages)} raw passages")

        # Clean and limit passages using HTMLTextCleaner (includes citation filtering)
        if raw_passages:
            cleaned_passages, cleaned_urls = self.text_cleaner.clean_and_limit_passages(
                raw_passages, raw_urls
            )

            total_chars = sum(len(p) for p in cleaned_passages)
            print(
                f"🎯 Final processed context: {len(cleaned_passages)} passages, {total_chars:,} characters"
            )

            return cleaned_passages, cleaned_urls
        else:
            print("⚠️ No passages collected")
            return [], []

    async def aforward(self, article_draft: str, k=None, **kwargs):

        with dspy.context(models=self.models["rag"].dspy_lm):
            topic_results = self.topic_extractor(draft_or_outline=article_draft).output

        if topic_results.needs_research:
            queries = topic_results.search_query
            print(f"Main topic identified: {topic_results.main_topic}")
            print(f"🔍 Extracted search queries: {queries}")
            queries = [
                topic_results.main_topic
            ] + queries  # Always include main topic at the front
        else:
            print("No research needed based on topic extraction.")
            return [], []

        k = k if k is not None else self.k
        passages, urls = await self.fetch_and_extract(queries, k)

        return passages, urls


if __name__ == "__main__":
    print("Part of a larger system; run main.py for end-to-end tests.")
