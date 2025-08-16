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
from typing import List, Union, Optional
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
from dspy_factory import get_current_lm, get_context_window, check_context_usage


# Load environment variables from .env file
load_dotenv()

# Configure logging - suppress verbose LiteLLM output
logging.basicConfig(level=logging.WARNING)  # Only show warnings and errors
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Keep INFO level for this module only

# Suppress LiteLLM verbose logging
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("litellm").setLevel(logging.WARNING)


class TavilyRetriever(dspy.Retrieve):
    def __init__(self, k=3, max_total_chars=None):
        super().__init__(k=k)
        self.tavily = AsyncTavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

        # Use context window management for intelligent sizing
        if max_total_chars is None:
            try:
                # Reserve space for prompts and output, use 60% of context for RAG content
                context_window = get_context_window()
                lm = get_current_lm()
                available_for_rag = int(
                    (context_window - lm.get_max_output_tokens()) * 0.6
                )
                max_total_chars = max(50000, available_for_rag)  # Minimum 50K chars
                print(
                    f"🧠 Auto-sizing RAG content to {max_total_chars:,} chars based on {context_window:,} token context window"
                )
            except Exception as e:
                logger.warning(
                    f"Could not determine context window, using default: {e}"
                )
                max_total_chars = 100000

        self.max_total_chars = max_total_chars
        self.text_cleaner = HTMLTextCleaner(max_total_chars=max_total_chars)
        dspy.settings.configure(rm=self)

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
                print(f"- {result.get('content', '')[:200]}...")

                if result.get("score", 0) > 0.5:
                    relevant_urls.append(result.get("url"))

        # Extract content from the relevant URLs
        extracted_data = await asyncio.gather(
            *(self.tavily.extract(url) for url in relevant_urls)
        )

        # Collect raw passages and URLs
        raw_passages = []
        raw_urls = []

        for data in extracted_data:
            results = data.get("results", [])
            if results:
                print(f"RAG results for {query}:")
                for result in results:
                    raw_content = result.get("raw_content", "")
                    url = result.get("url", "")

                    if raw_content and url:  # Only add if both content and URL exist
                        raw_passages.append(raw_content)
                        raw_urls.append(url)
                        print(f"- {url[:100]}...")
                        print(f"- {raw_content[:100]}...")
                        print(f"Content length - {len(raw_content)} characters")

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

    async def aforward(self, queries: List[str], k=None, **kwargs):

        k = k if k is not None else self.k
        passages, urls = await self.fetch_and_extract(queries, k)

        return passages, urls


class TavilyRAGModule(dspy.Module):
    """
    A complete RAG module using TavilyRM for retrieval and markdown generation.
    """

    def __init__(
        self,
        k: int = 3,
        include_raw_content: bool = True,
        max_total_chars: Optional[int] = None,
    ):
        """
        Initialize the Tavily RAG module.

        Args:
            k (int): Number of results to retrieve
            include_raw_content (bool): Whether to include raw content from pages
            max_total_chars (Optional[int]): Maximum total characters across all passages.
                                           If None, auto-calculated based on context window.
        """
        super().__init__()
        self.retrieve = TavilyRetriever(k=k, max_total_chars=max_total_chars)
        self.k = k

    def forward(self, queries: List[str]) -> dspy.Prediction:
        """
        Process a queries through retrieval and markdown generation.

        Args:
            queries (str): The queries to answer

        Returns:
            dspy.Prediction: Contains the queries, retrieved context, and markdown answer
        """
        try:
            # Retrieve relevant passages and URLs
            [passages, urls] = asyncio.run(self.retrieve.aforward(queries))

            logger.info(f"Retrieved {len(passages)} passages and {len(urls)} URLs")

            return dspy.Prediction(
                passages=passages,
                urls=urls,
            )

        except Exception as e:
            logger.error(f"Error in TavilyRAGModule forward pass: {str(e)}")
            return dspy.Prediction(
                passages=[],
                urls=[],
            )


# Example usage and testing functions
def test_rag_system():
    """
    Test function to demonstrate RAG system functionality.
    """
    try:

        # Test full RAG module (requires DSPy LM configuration)
        print("\n" + "=" * 50)
        print("Testing full RAG module...")

        # Note: This requires proper DSPy LM configuration
        rag_module = TavilyRAGModule(k=10)
        response = rag_module("What are the latest developments in AI for 2025?")

        print("RAG system test completed successfully!")

    except Exception as e:
        print(f"Error in test: {str(e)}")


if __name__ == "__main__":
    # Run tests when module is executed directly
    test_rag_system()
