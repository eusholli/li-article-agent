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

# Load environment variables from .env file
load_dotenv()

# Configure logging - suppress verbose LiteLLM output
logging.basicConfig(level=logging.WARNING)  # Only show warnings and errors
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Keep INFO level for this module only

# Suppress LiteLLM verbose logging
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("litellm").setLevel(logging.WARNING)


import dspy
from tavily import TavilyClient
from typing import List, Union
from dspy import Prediction


class TavilyRM(dspy.Retrieve):
    def __init__(self, k: int = 3, include_raw_content: bool = False):
        super().__init__(k=k)
        self.tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        self.include_raw_content = include_raw_content

    def forward(self, query, k=None, **kwargs):
        k = k if k is not None else self.k
        queries = [query] if isinstance(query, str) else query

        # Initialize lists to store results
        passages = []
        urls = []

        for query in queries:
            # Perform Tavily search with raw content
            response = self.tavily_client.search(
                query=query,
                max_results=self.k,
                include_raw_content=self.include_raw_content,
            )

            # Extract raw content and URLs from results
            for result in response.get("results", []):
                content = result.get("raw_content", result.get("content", ""))
                url = result.get("url", "")
                if content and url:  # Ensure both are present
                    passages.append(content)
                    urls.append(url)

        # Return a Prediction object with passages and URLs
        return Prediction(passages=passages, urls=urls[: self.k])


class TavilyRetriever(dspy.Retrieve):
    def __init__(self, k=3):
        super().__init__(k=k)
        self.tavily = AsyncTavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        dspy.settings.configure(rm=self)

    async def fetch_and_extract(self, query: str, k: int):

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
        print("End of RAG responses")

        passages = []
        urls = []

        for data in extracted_data:
            results = data.get("results", [])
            if results:
                print(f"RAG results for {query}:")
                for result in results:
                    passages.append(result.get("raw_content", ""))
                    urls.append(result.get("url", ""))
                    print(f"- {result.get('url', '')[:100]}...")
                    print(f"- {result.get('raw_content', '')[:100]}...")

        return passages, urls

    async def aforward(self, query, k=None, **kwargs):

        k = k if k is not None else self.k
        passages, urls = await self.fetch_and_extract(query, k)

        return passages, urls


class MarkdownGenerator(dspy.Signature):
    """Generate a markdown paragraph with inline URL citations based on retrieved context."""

    question = dspy.InputField(desc="The question to answer")
    passages = dspy.InputField(
        desc="Retrieved text passages containing relevant information"
    )
    urls = dspy.InputField(desc="URLs corresponding to the passages")
    markdown_answer = dspy.OutputField(
        desc="A well-structured markdown paragraph answering the question with inline URL citations in the format [text](url)"
    )


class TavilyRAGModule(dspy.Module):
    """
    A complete RAG module using TavilyRM for retrieval and markdown generation.
    """

    def __init__(self, k: int = 3, include_raw_content: bool = True):
        """
        Initialize the Tavily RAG module.

        Args:
            k (int): Number of results to retrieve
            include_raw_content (bool): Whether to include raw content from pages
        """
        super().__init__()
        self.retrieve = TavilyRetriever(k=k)
        self.generate_markdown = dspy.ChainOfThought(MarkdownGenerator)
        self.k = k

    def forward(self, question: str) -> dspy.Prediction:
        """
        Process a question through retrieval and markdown generation.

        Args:
            question (str): The question to answer

        Returns:
            dspy.Prediction: Contains the question, retrieved context, and markdown answer
        """
        try:
            # Retrieve relevant passages and URLs
            [passages, urls] = asyncio.run(self.retrieve.aforward(question))

            logger.info(f"Retrieved {len(passages)} passages and {len(urls)} URLs")

            # Generate markdown answer with citations
            markdown_result = self.generate_markdown(
                question=question, passages=passages, urls=urls
            )

            return dspy.Prediction(
                question=question,
                passages=passages,
                urls=urls,
                markdown_answer=markdown_result.markdown_answer,
            )

        except Exception as e:
            logger.error(f"Error in TavilyRAGModule forward pass: {str(e)}")
            return dspy.Prediction(
                question=question,
                passages=[],
                urls=[],
                markdown_answer=f"Error processing question: {str(e)}",
            )


class WebSearchRetriever(dspy.Retrieve):
    """
    A custom retriever that uses DuckDuckGo Search to find relevant web pages.

    This class inherits from dspy.Retrieve and implements web search functionality
    that can be used as a Retrieval Model (RM) in DSPy configurations.
    """

    def __init__(self, k: int = 5):
        """
        Initialize the web search retriever.

        Args:
            k (int): The default number of results to retrieve. Defaults to 5.
        """
        super().__init__(k=k)
        self.ddgs = DDGS()
        logger.info(f"TavilyRetriever initialized with k={k}")

    def forward(self, query: str, k: Optional[int] = None, **kwargs) -> List[str]:
        """
        The core retrieval logic that performs web search.

        Args:
            query (str): The query to search for.
            k (int, optional): The number of results to retrieve. Defaults to self.k.
            **kwargs: Additional arguments for compatibility.

        Returns:
            List[str]: A list of search result texts.
        """
        k = k if k is not None else self.k

        try:
            logger.info(f"Searching for: {query}")

            # Perform the search using DuckDuckGo
            results = self.ddgs.text(query, max_results=k)

            # Format the results into a list of strings
            # We combine the title and snippet for better context
            formatted_results = [
                f"Title: {res['title']}\nSnippet: {res['body']}" for res in results
            ]

            logger.info(
                f"Retrieved {len(formatted_results)} results for query: {query}"
            )
            return formatted_results

        except Exception as e:
            logger.error(f"Error searching for query '{query}': {str(e)}")
            return []


class GenerateAnswer(dspy.Signature):
    """Answer questions based on the provided context from web search results."""

    context = dspy.InputField(desc="Relevant information retrieved from web search")
    question = dspy.InputField(desc="The question to answer based on the context")
    answer = dspy.OutputField(
        desc="A comprehensive answer based on the retrieved context"
    )


class RAGModule(dspy.Module):
    """
    Complete RAG (Retrieval-Augmented Generation) module.

    This module combines web search retrieval with answer generation to provide
    comprehensive responses to questions using up-to-date web information.
    """

    def __init__(self, k: int = 5):
        """
        Initialize the RAG module.

        Args:
            k (int): Number of search results to retrieve. Defaults to 5.
        """
        super().__init__()
        self.retrieve = dspy.Retrieve(k=k)  # Will use the configured TavilyRetriever
        self.generate_answer = dspy.ChainOfThought(GenerateAnswer)
        self.k = k
        logger.info(f"RAGModule initialized with k={k}")

    def forward(self, question: str) -> dspy.Prediction:
        """
        Process a question through the complete RAG pipeline.

        Args:
            question (str): The question to answer.

        Returns:
            dspy.Prediction: Contains both the retrieved context and generated answer.
        """
        try:
            # Retrieve relevant context from web search
            context_results = self.retrieve(question)

            # Handle different return types from retrieve
            if isinstance(context_results, list):
                context = context_results
            elif hasattr(context_results, "passages"):
                context = context_results.passages
            else:
                context = []

            # Generate answer based on retrieved context
            prediction = self.generate_answer(context=context, question=question)

            # Return prediction with both context and answer
            return dspy.Prediction(
                context=context, answer=prediction.answer, question=question
            )

        except Exception as e:
            logger.error(f"Error in RAG forward pass: {str(e)}")
            return dspy.Prediction(
                context=[],
                answer=f"Error processing question: {str(e)}",
                question=question,
            )


def search_and_retrieve(query: str, k: int = 5) -> List[str]:
    """
    Simple function interface for web search retrieval.

    This function provides a straightforward way to search the web and retrieve
    k maximum results without the full RAG pipeline.

    Args:
        query (str): The search query.
        k (int): Maximum number of results to return. Defaults to 5.

    Returns:
        List[str]: List of search result texts (title + snippet).
    """
    try:
        # Create a temporary retriever instance
        retriever = TavilyRetriever(k=k)

        # Perform the search - returns List[str] directly
        search_results = asyncio.run(retriever.aforward(query, k=k))

        # search_results = retriever.forward(query, k=k)

        logger.info(
            f"search_and_retrieve returned {len(search_results)} results for query: {query}"
        )
        return search_results

    except Exception as e:
        logger.error(f"Error in search_and_retrieve: {str(e)}")
        return []


def configure_rag_system(lm_model=None, k: int = 5) -> RAGModule:
    """
    Configure the complete RAG system with web search capabilities.

    This function sets up DSPy with a web search retriever and returns a
    configured RAG module ready for use.

    Args:
        lm_model: The language model to use. If None, uses current dspy.settings.
        k (int): Number of search results to retrieve. Defaults to 5.

    Returns:
        RAGModule: Configured RAG module ready for use.
    """
    try:
        # Create web search retriever
        web_retriever = TavilyRetriever(k=k)

        # Configure DSPy settings if language model provided
        if lm_model is not None:
            dspy.settings.configure(lm=lm_model, rm=web_retriever)
        else:
            # Just configure the retrieval model
            dspy.settings.configure(rm=web_retriever)

        # Create and return RAG module
        rag_module = RAGModule(k=k)

        logger.info(f"RAG system configured successfully with k={k}")
        return rag_module

    except Exception as e:
        logger.error(f"Error configuring RAG system: {str(e)}")
        raise


# Example usage and testing functions
def test_rag_system():
    """
    Test function to demonstrate RAG system functionality.
    """
    try:
        # Test simple search and retrieve
        print("Testing search_and_retrieve function...")
        results = search_and_retrieve("Rakuten Symphony Cloud", k=3)

        print(f"Retrieved {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"\n[{i}] {result[:200]}...")

        # Test full RAG module (requires DSPy LM configuration)
        print("\n" + "=" * 50)
        print("Testing full RAG module...")

        # Note: This requires proper DSPy LM configuration
        # rag_module = configure_rag_system(k=3)
        # response = rag_module("What are the latest developments in AI for 2025?")
        # print(f"Question: {response.question}")
        # print(f"Answer: {response.answer}")

        print("RAG system test completed successfully!")

    except Exception as e:
        print(f"Error in test: {str(e)}")


if __name__ == "__main__":
    # Run tests when module is executed directly
    test_rag_system()
