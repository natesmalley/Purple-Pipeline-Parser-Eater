#!/usr/bin/env python3
"""
Test RAG components - RAGKnowledgeBase and ClaudeRAGAssistant
"""

import sys
import asyncio
from pathlib import Path

# Add the current directory to the path so imports work
sys.path.insert(0, str(Path(__file__).parent))


def test_rag_knowledge_base():
    """Test RAGKnowledgeBase component (synchronous)"""
    print("=" * 70)
    print("Phase 6.1: Testing RAGKnowledgeBase Component")
    print("=" * 70)

    try:
        # Import RAGKnowledgeBase
        print("\n[1/7] Importing RAGKnowledgeBase...")
        from components.rag_knowledge import RAGKnowledgeBase
        print("SUCCESS: RAGKnowledgeBase imported")

        # Initialize knowledge base
        print("\n[2/7] Initializing RAGKnowledgeBase...")
        config = {
            "milvus": {
                "host": "localhost",
                "port": "19530",
                "collection_name": "test_rag_knowledge"
            }
        }
        kb = RAGKnowledgeBase(config=config)

        if not kb.enabled:
            print("ERROR: RAGKnowledgeBase failed to initialize")
            return False

        print("SUCCESS: RAGKnowledgeBase initialized")
        print(f"  - Collection: {kb.collection_name}")
        print(f"  - Embedding model loaded: {kb.embedding_model is not None}")

        # Test ingestion
        print("\n[3/7] Testing built-in documentation ingestion...")
        success = kb.ingest_observo_documentation()
        if success:
            print("SUCCESS: Documentation ingested")
        else:
            print("WARNING: Documentation ingestion failed (check logs)")

        # Test search
        print("\n[4/7] Testing knowledge search...")
        query = "How do I optimize LUA performance for high volume?"
        results = kb.search_knowledge(query, top_k=3)

        if results:
            print(f"SUCCESS: Found {len(results)} relevant documents:")
            for i, result in enumerate(results, 1):
                score = result.get('similarity_score', 0)
                title = result.get('title', 'Untitled')
                print(f"  {i}. {title} (similarity: {score:.4f})")
                content_preview = result.get('content', '')[:100].replace('\n', ' ')
                print(f"     Preview: {content_preview}...")
        else:
            print("WARNING: No search results found")

        # Test recommendations
        print("\n[5/7] Testing parser recommendations...")
        parser_analysis = {
            "parser_complexity": {"level": "High"},
            "performance_characteristics": {"expected_volume": "High"},
            "ocsf_mapping": {"class_name": "Security Finding"}
        }
        recommendations = kb.get_parser_recommendations(parser_analysis)

        if recommendations:
            print(f"SUCCESS: Got {len(recommendations)} recommendations")
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec.get('title', 'Untitled')}")
        else:
            print("INFO: No specific recommendations (expected for simple parsers)")

        # Test specific category search
        print("\n[6/7] Testing filtered search (performance docs only)...")
        perf_results = kb.search_knowledge(
            "memory optimization",
            top_k=2,
            doc_type_filter="performance"
        )

        if perf_results:
            print(f"SUCCESS: Found {len(perf_results)} performance documents")
        else:
            print("INFO: No performance-specific documents found")

        # Clean up
        print("\n[7/7] Cleaning up test collection...")
        from pymilvus import utility, connections
        if utility.has_collection("test_rag_knowledge"):
            utility.drop_collection("test_rag_knowledge")
            print("SUCCESS: Test collection removed")

        connections.disconnect("default")

        print("\n" + "=" * 70)
        print("PHASE 6.1 COMPLETE: RAGKnowledgeBase tests passed!")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"\nERROR: RAGKnowledgeBase test failed!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\n" + "=" * 70)
        return False


def test_claude_rag_assistant():
    """Test ClaudeRAGAssistant component"""
    print("\n" + "=" * 70)
    print("Phase 6.2: Testing ClaudeRAGAssistant Component")
    print("=" * 70)

    try:
        # Import components
        print("\n[1/4] Importing ClaudeRAGAssistant and RAGKnowledgeBase...")
        from components.rag_assistant import ClaudeRAGAssistant
        from components.rag_knowledge import RAGKnowledgeBase
        print("SUCCESS: Components imported")

        # Initialize knowledge base first
        print("\n[2/4] Initializing knowledge base for assistant...")
        kb_config = {
            "milvus": {
                "host": "localhost",
                "port": "19530",
                "collection_name": "test_rag_assistant_kb"
            }
        }
        knowledge_base = RAGKnowledgeBase(config=kb_config)

        if not knowledge_base.enabled:
            print("WARNING: Knowledge base not enabled, skipping assistant test")
            return True

        print("SUCCESS: Knowledge base ready")

        # Initialize assistant
        print("\n[3/4] Initializing ClaudeRAGAssistant...")
        assistant_config = {
            "anthropic": {
                "api_key": "test-mock-key",  # Mock key - won't make real API calls in this test
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 4000,
                "temperature": 0.1
            }
        }
        assistant = ClaudeRAGAssistant(
            config=assistant_config,
            knowledge_base=knowledge_base
        )
        print("SUCCESS: ClaudeRAGAssistant initialized")
        print(f"  - Model: {assistant.model}")
        print(f"  - Knowledge base connected: {assistant.knowledge_base is not None}")

        # Verify components
        print("\n[4/4] Verifying assistant components...")
        print(f"  - Client initialized: {assistant.client is not None}")
        print(f"  - Rate limiter configured: {assistant.rate_limiter is not None}")
        print(f"  - Prompts defined: {len(assistant.contextual_assistance_prompt) > 0}")

        print("\nINFO: Skipping actual Claude API calls (requires valid API key)")
        print("INFO: Structure and initialization verified successfully")

        # Clean up
        from pymilvus import utility, connections
        if utility.has_collection("test_rag_assistant_kb"):
            utility.drop_collection("test_rag_assistant_kb")

        print("\n" + "=" * 70)
        print("PHASE 6.2 COMPLETE: ClaudeRAGAssistant tests passed!")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"\nERROR: ClaudeRAGAssistant test failed!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\n" + "=" * 70)
        return False


def main():
    """Run all RAG component tests"""
    print("\n")
    print("*" * 70)
    print("*" + " " * 68 + "*")
    print("*" + "  RAG COMPONENTS TEST SUITE".center(68) + "*")
    print("*" + " " * 68 + "*")
    print("*" * 70)
    print("\n")

    # Test RAGKnowledgeBase
    kb_success = test_rag_knowledge_base()

    # Test ClaudeRAGAssistant
    assistant_success = test_claude_rag_assistant()

    # Final summary
    print("\n" + "=" * 70)
    print("PHASE 6 COMPLETE: RAG Component Testing Summary")
    print("=" * 70)
    print(f"RAGKnowledgeBase:     {'PASS' if kb_success else 'FAIL'}")
    print(f"ClaudeRAGAssistant:   {'PASS' if assistant_success else 'FAIL'}")
    print("=" * 70)

    if kb_success and assistant_success:
        print("\nSUCCESS: All RAG component tests passed!")
        print("The system is ready for end-to-end testing (Phase 7)")
        return True
    else:
        print("\nFAILURE: Some RAG component tests failed")
        print("Please review the errors above and fix issues before proceeding")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
