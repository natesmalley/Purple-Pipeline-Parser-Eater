#!/usr/bin/env python3
"""W10/T2 — RAG component smoke tests (skipped by default).

These tests exercise the optional RAG stack (Milvus + sentence-transformers
+ Anthropic). They are skipped at the module level because:

1. Milvus must be reachable at ``localhost:19530`` (only true on the
   docker-compose dev stack), and
2. End-to-end RAG integration is already covered by ``test_rag_components.py``.

The previous version of this module returned ``True``/``False`` from each
``test_*`` function, which Pytest >=8 treats as ``PytestReturnNotNoneWarning``.
The bodies below now use ``assert`` so the warning no longer surfaces. The
module-level skip means the tests don't run in CI; the asserts only fire
if a developer explicitly removes the skip mark to re-enable the suite.
"""

import sys
from pathlib import Path

import pytest


# Module-level skip — these tests need a running Milvus instance and are
# duplicated by tests/test_rag_components.py for the integration path.
pytestmark = pytest.mark.skip(
    reason=(
        "RAG components are optional; integration covered by "
        "tests/test_rag_components.py and requires Milvus on localhost:19530."
    )
)


# Add the project root to the path so imports work when this module is
# re-enabled by removing the pytestmark above.
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_rag_knowledge_base():
    """Test RAGKnowledgeBase component (synchronous)."""
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

        assert kb.enabled, "RAGKnowledgeBase failed to initialize"

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

    except Exception as e:
        import traceback
        traceback.print_exc()
        pytest.fail(
            f"RAGKnowledgeBase test failed: {type(e).__name__}: {e}"
        )


def test_claude_rag_assistant():
    """Test ClaudeRAGAssistant component."""
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
            pytest.skip("Knowledge base not enabled, skipping assistant test")

        print("SUCCESS: Knowledge base ready")

        # Initialize assistant
        print("\n[3/4] Initializing ClaudeRAGAssistant...")
        assistant_config = {
            "anthropic": {
                # Mock key - won't make real API calls in this test
                "api_key": "test-mock-key",
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
        assert assistant.client is not None, "assistant.client must be initialized"
        assert assistant.rate_limiter is not None, "rate_limiter must be configured"
        assert len(assistant.contextual_assistance_prompt) > 0, (
            "contextual_assistance_prompt must be defined"
        )

        print("\nINFO: Skipping actual Claude API calls (requires valid API key)")
        print("INFO: Structure and initialization verified successfully")

        # Clean up
        from pymilvus import utility, connections
        if utility.has_collection("test_rag_assistant_kb"):
            utility.drop_collection("test_rag_assistant_kb")

        print("\n" + "=" * 70)
        print("PHASE 6.2 COMPLETE: ClaudeRAGAssistant tests passed!")
        print("=" * 70)

    except Exception as e:
        import traceback
        traceback.print_exc()
        pytest.fail(
            f"ClaudeRAGAssistant test failed: {type(e).__name__}: {e}"
        )
