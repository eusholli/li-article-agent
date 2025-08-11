#!/usr/bin/env python3
"""
Demonstration script for the RAG module

This script shows how to use the search_and_retrieve function to get k max results
from web search as requested in the task.
"""

from rag import search_and_retrieve, configure_rag_system
import sys


def demo_search_and_retrieve():
    """
    Demonstrate the search_and_retrieve function that takes a query
    and returns k max results from search retrieval.
    """
    print("=" * 60)
    print("RAG Module Demo - search_and_retrieve function")
    print("=" * 60)

    # Example queries to demonstrate the functionality
    queries = [
        "artificial intelligence trends 2025",
        "LinkedIn content strategy best practices",
        "DSPy framework tutorial",
    ]

    for i, query in enumerate(queries, 1):
        print(f"\n{i}. Query: '{query}'")
        print("-" * 50)

        # Use the search_and_retrieve function with k=3 results
        results = search_and_retrieve(query, k=3)

        if results:
            print(f"Retrieved {len(results)} results:")
            for j, result in enumerate(results, 1):
                print(f"\n  [{j}] {result[:150]}...")
        else:
            print("No results found.")

        print()


def demo_different_k_values():
    """
    Demonstrate how the k parameter controls the number of results returned.
    """
    print("=" * 60)
    print("Demonstrating different k values")
    print("=" * 60)

    query = "machine learning applications"
    k_values = [1, 3, 5]

    for k in k_values:
        print(f"\nSearching for '{query}' with k={k}:")
        print("-" * 40)

        results = search_and_retrieve(query, k=k)
        print(f"Returned {len(results)} results")

        for i, result in enumerate(results, 1):
            # Show just the title for brevity
            title_line = result.split("\n")[0]
            print(f"  {i}. {title_line}")


def main():
    """
    Main demonstration function
    """
    print("RAG Module Demonstration")
    print("This demonstrates the search_and_retrieve function that:")
    print("- Takes a query string as input")
    print("- Returns k maximum results from web search retrieval")
    print("- Uses DuckDuckGo search via the ddgs library")
    print("- Integrates with DSPy framework patterns")

    try:
        # Demo 1: Basic search_and_retrieve functionality
        demo_search_and_retrieve()

        # Demo 2: Different k values
        demo_different_k_values()

        print("\n" + "=" * 60)
        print("Demo completed successfully!")
        print("=" * 60)

        print("\nKey Features Demonstrated:")
        print("✓ search_and_retrieve(query, k) function")
        print("✓ Configurable number of results (k parameter)")
        print("✓ Web search integration via DuckDuckGo")
        print("✓ Formatted results with titles and snippets")
        print("✓ Error handling and logging")

    except Exception as e:
        print(f"Error during demonstration: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
