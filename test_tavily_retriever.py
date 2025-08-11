"""
Test program for TavilyRetriever in rag.py

This program demonstrates how to use the TavilyRM retriever to:
1. Retrieve relevant passages and URLs for a given question
2. Generate a markdown paragraph with inline URL citations
3. Use the dspy.Retriever pattern effectively
"""

from dspy_factory import setup_dspy_provider
import asyncio
import dspy
import os
from dotenv import load_dotenv
from rag import TavilyRetriever
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


def test_tavily_retriever_basic():
    """Test basic TavilyRM functionality."""
    print("=" * 60)
    print("Testing Basic TavilyRM Retrieval")
    print("=" * 60)

    # Initialize the retriever
    retriever = TavilyRetriever(k=3)

    # Test query
    query = "What are the latest developments in 6G technology?"

    try:
        # Perform retrieval
        result = retriever.forward(query)

        print(f"Query: {query}")
        print(
            f"Retrieved {len(result.passages)} passages and {len(result.urls)} URLs\n"
        )

        # Display results
        for i, (passage, url) in enumerate(zip(result.passages, result.urls), 1):
            print(f"[{i}] URL: {url}")
            print(f"    Content: {passage[:200]}...")
            print()

        return result

    except Exception as e:
        print(f"Error in basic test: {str(e)}")
        return None


def test_markdown_generation(lm_model=None):
    """Test the complete RAG pipeline with markdown generation."""
    print("=" * 60)
    print("Testing Complete RAG Pipeline with Markdown Generation")
    print("=" * 60)

    # Configure DSPy with a language model if provided
    setup_dspy_provider()

    # Initialize the RAG module
    rag_module = TavilyRAGModule(k=3, include_raw_content=True)

    # Test questions
    test_questions = [
        "What are the key benefits of 6G technology over 5G?",
        "How is artificial intelligence being integrated into telecommunications?",
        "What are the latest trends in cloud computing for 2024?",
    ]

    for question in test_questions:
        print(f"Question: {question}")
        print("-" * 40)

        try:
            # Process the question
            result = rag_module(question)

            print("Retrieved Sources:")
            for i, url in enumerate(result.urls, 1):
                print(f"  [{i}] {url}")

            print(f"\nMarkdown Answer:")
            print(result.markdown_answer)
            print("\n" + "=" * 60 + "\n")

        except Exception as e:
            print(f"Error processing question: {str(e)}\n")


def interactive_test():
    """Interactive test allowing user to input custom questions."""
    print("=" * 60)
    print("Interactive TavilyRetriever Test")
    print("=" * 60)
    print("Enter your questions (type 'quit' to exit)")

    # Initialize the RAG module
    rag_module = TavilyRAGModule(k=3, include_raw_content=True)

    while True:
        question = input("\nYour question: ").strip()

        if question.lower() in ["quit", "exit", "q"]:
            break

        if not question:
            continue

        try:
            print("\nProcessing...")
            result = rag_module(question)

            print(f"\nRetrieved {len(result.urls)} sources:")
            for i, url in enumerate(result.urls, 1):
                print(f"  [{i}] {url}")

            print(f"\nMarkdown Answer:")
            print(result.markdown_answer)

        except Exception as e:
            print(f"Error: {str(e)}")


def main():
    """Main test function."""
    print("TavilyRetriever Test Program")
    print("=" * 60)

    # Check for Tavily API key
    if not os.getenv("TAVILY_API_KEY"):
        print("ERROR: TAVILY_API_KEY not found in environment variables.")
        print("Please set your Tavily API key in the .env file.")
        return

    # Test 2: Try markdown generation (may require LM configuration)
    print("\nAttempting markdown generation test...")
    print("Note: This requires a configured language model in DSPy")

    try:
        test_markdown_generation()
    except Exception as e:
        print(f"Markdown generation test failed: {str(e)}")
        print("This is expected if no language model is configured in DSPy")

    # Test 3: Interactive mode
    try:
        interactive_test()
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    except Exception as e:
        print(f"Interactive test error: {str(e)}")


if __name__ == "__main__":
    main()
