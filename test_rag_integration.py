#!/usr/bin/env python3
"""
Test script for TavilyRAGModule integration with LinkedIn Article Generation

This script tests the complete integration of TavilyRAGModule with the article
generation system, including citation-controlled markdown output.
"""

import os
from linkedin_article_react import LinkedInArticleREACT
from dspy_factory import setup_dspy_provider


def test_rag_integration():
    """Test the TavilyRAGModule integration with article generation."""

    print("🧪 Testing TavilyRAGModule Integration")
    print("=" * 50)

    # Configure DSPy with language model
    try:
        lm = setup_dspy_provider()
        print(f"✅ DSPy configured with model: {lm.model}")
    except SystemExit:
        print("❌ Failed to configure DSPy - missing OPENROUTER_API_KEY")
        return
    except Exception as e:
        print(f"❌ Failed to configure DSPy: {e}")
        return

    # Check if Tavily API key is available
    if not os.getenv("TAVILY_API_KEY"):
        print("⚠️ TAVILY_API_KEY not found in environment variables")
        print("Please set your Tavily API key to test RAG integration")
        return

    # Initialize the REACT generator with TavilyRAGModule
    try:
        react_generator = LinkedInArticleREACT(
            target_score_percentage=85.0,  # Lower target for testing
            max_iterations=2,  # Fewer iterations for testing
            rag_k=3,  # Fewer search results for testing
        )
        print("✅ LinkedInArticleREACT initialized successfully")
        print(f"✅ RAG available: {react_generator.rag_available}")

    except Exception as e:
        print(f"❌ Failed to initialize LinkedInArticleREACT: {e}")
        return

    # Test draft that should trigger research
    test_draft = """
    # The Impact of AI on Software Development in 2024
    
    Artificial Intelligence is revolutionizing how we write, test, and deploy code.
    
    Key areas of transformation:
    - Code generation and completion
    - Automated testing and bug detection
    - DevOps and deployment automation
    - Code review and quality assurance
    
    This transformation is happening faster than many developers expected.
    """

    print(f"\n📝 Test Draft:")
    print(test_draft)
    print("\n" + "=" * 50)

    # Generate article with RAG integration
    try:
        print("🚀 Starting article generation with RAG integration...")
        result = react_generator.generate_article(test_draft, verbose=True)

        print("\n" + "=" * 50)
        print("📊 INTEGRATION TEST RESULTS")
        print("=" * 50)

        # Check REACT metadata
        react_metadata = result.get("react_metadata", {})
        print(f"🧠 Main Topic: {react_metadata.get('main_topic', 'N/A')}")
        print(f"🔍 Research Needed: {react_metadata.get('needs_research', 'N/A')}")
        print(
            f"🌐 Research Performed: {react_metadata.get('research_performed', 'N/A')}"
        )
        print(
            f"📄 Context Length: {react_metadata.get('context_length', 0)} characters"
        )

        # Check final article
        final_article = result.get("final_article", "")
        print(f"\n📝 Final Article Length: {len(final_article)} characters")

        final_score = result.get("final_score")
        if final_score:
            print(f"📊 Final Score: {final_score.percentage:.1f}%")
        else:
            print("📊 Final Score: N/A")

        print(f"🎯 Target Achieved: {result.get('target_achieved', False)}")

        # Check for markdown formatting
        has_headers = "#" in final_article
        has_bold = "**" in final_article
        has_links = "[" in final_article and "](" in final_article

        print(f"\n📋 MARKDOWN FORMATTING CHECK:")
        print(f"  ✅ Headers: {'Yes' if has_headers else 'No'}")
        print(f"  ✅ Bold text: {'Yes' if has_bold else 'No'}")
        print(f"  ✅ Links/Citations: {'Yes' if has_links else 'No'}")

        # Show a preview of the final article
        print(f"\n📄 ARTICLE PREVIEW (first 500 chars):")
        print("-" * 30)
        print(
            final_article[:500] + "..." if len(final_article) > 500 else final_article
        )
        print("-" * 30)

        # Test export functionality
        try:
            export_path = "test_rag_integration_results.json"
            react_generator.export_results(export_path)
            print(f"\n💾 Results exported to: {export_path}")
        except Exception as e:
            print(f"\n⚠️ Export failed: {e}")

        print("\n✅ RAG Integration Test Completed Successfully!")

    except Exception as e:
        print(f"\n❌ Article generation failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_rag_integration()
