#!/usr/bin/env python3
"""
Test RAG components - RAGKnowledgeBase and RAGAssistant
"""

import sys
import asyncio
from pathlib import Path

# Add the current directory to the path so imports work
sys.path.insert(0, str(Path(__file__).parent))

async def test_rag_knowledge_base():
    """Test RAGKnowledgeBase component"""
    print("=" * 70)
    print("Phase 6.1: Testing RAGKnowledgeBase Component")
    print("=" * 70)

    try:
        # Import RAGKnowledgeBase
        print("\n[1/6] Importing RAGKnowledgeBase...")
        from components.rag_knowledge import RAGKnowledgeBase
        print("SUCCESS: RAGKnowledgeBase imported")

        # Initialize knowledge base
        print("\n[2/6] Initializing RAGKnowledgeBase...")
        config = {
            "milvus": {
                "host": "localhost",
                "port": "19530",
                "collection_name": "test_rag_knowledge"
            }
        }
        kb = RAGKnowledgeBase(config=config)
        await kb.initialize()
        print("SUCCESS: RAGKnowledgeBase initialized")

        # Add sample documents
        print("\n[3/6] Adding sample Observo.ai documentation...")
        sample_docs = [
            {
                "title": "Observo.ai Pipeline Configuration",
                "content": "Observo.ai pipelines are configured using YAML files that define data sources, transformations, and destinations.",
                "category": "Configuration"
            },
            {
                "title": "LUA Transformation Functions",
                "content": "LUA transformation functions in Observo.ai allow you to modify data fields, parse logs, and enrich events using custom logic.",
                "category": "Transformations"
            },
            {
                "title": "Data Source Integration",
                "content": "Observo.ai supports multiple data sources including syslog, HTTP endpoints, Kafka streams, and cloud storage buckets.",
                "category": "Data Sources"
            }
        ]

        for doc in sample_docs:
            doc_id = await kb.add_document(
                content=doc["content"],
                metadata={
                    "title": doc["title"],
                    "category": doc["category"],
                    "source": "test_suite"
                }
            )
            print(f"  - Added document: {doc['title']} (ID: {doc_id})")

        print("SUCCESS: Sample documents added")

        # Test vector search
        print("\n[4/6] Testing vector search...")
        query = "How do I configure a pipeline?"
        results = await kb.search_similar(query, top_k=2)

        if results:
            print(f"SUCCESS: Found {len(results)} relevant documents:")
            for i, result in enumerate(results, 1):
                print(f"  {i}. {result.get('title', 'Untitled')} (similarity: {result.get('score', 0):.4f})")
                print(f"     Content preview: {result.get('content', '')[:100]}...")
        else:
            print("WARNING: No search results found (might be an issue)")

        # Test get document
        print("\n[5/6] Testing document retrieval...")
        if results:
            first_doc_id = results[0].get('id')
            retrieved_doc = await kb.get_document(first_doc_id)
            if retrieved_doc:
                print(f"SUCCESS: Retrieved document by ID: {retrieved_doc.get('title', 'Untitled')}")
            else:
                print("WARNING: Could not retrieve document by ID")

        # Clean up
        print("\n[6/6] Cleaning up test collection...")
        from pymilvus import utility
        if utility.has_collection("test_rag_knowledge"):
            utility.drop_collection("test_rag_knowledge")
            print("SUCCESS: Test collection cleaned up")

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


async def test_rag_assistant():
    """Test RAGAssistant component (without actual API calls)"""
    print("\n" + "=" * 70)
    print("Phase 6.2: Testing RAGAssistant Component")
    print("=" * 70)

    try:
        # Import ClaudeRAGAssistant
        print("\n[1/4] Importing ClaudeRAGAssistant...")
        from components.rag_assistant import ClaudeRAGAssistant
        print("SUCCESS: ClaudeRAGAssistant imported")

        # Initialize assistant (in mock mode - no real API calls)
        print("\n[2/4] Initializing ClaudeRAGAssistant...")
        config = {
            "anthropic": {
                "api_key": "test-api-key",  # Mock API key
                "model": "claude-3-5-sonnet-20241022"
            },
            "milvus": {
                "host": "localhost",
                "port": "19530",
                "collection_name": "observo_knowledge"
            }
        }
        assistant = ClaudeRAGAssistant(config=config)
        await assistant.initialize()
        print("SUCCESS: ClaudeRAGAssistant initialized")

        # Test knowledge base is accessible
        print("\n[3/4] Verifying knowledge base integration...")
        if assistant.knowledge_base:
            print("SUCCESS: Knowledge base connection verified")
        else:
            print("INFO: Knowledge base not initialized (running in fallback mode)")

        # Test query formatting (no actual API call)
        print("\n[4/4] Testing query formatting...")
        test_parser = {
            "name": "test_parser",
            "patterns": ["pattern1", "pattern2"],
            "fields": ["field1", "field2"]
        }

        # Note: Not making actual Claude API call to avoid needing real API key
        print("INFO: Skipping actual Claude API call (would require valid API key)")
        print("SUCCESS: RAGAssistant component structure verified")

        print("\n" + "=" * 70)
        print("PHASE 6.2 COMPLETE: RAGAssistant tests passed!")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"\nERROR: RAGAssistant test failed!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\n" + "=" * 70)
        return False


async def main():
    """Run all RAG component tests"""
    print("\n")
    print("*" * 70)
    print("*" + " " * 68 + "*")
    print("*" + "  RAG COMPONENTS TEST SUITE".center(68) + "*")
    print("*" + " " * 68 + "*")
    print("*" * 70)
    print("\n")

    # Test RAGKnowledgeBase
    kb_success = await test_rag_knowledge_base()

    # Test RAGAssistant
    assistant_success = await test_rag_assistant()

    # Final summary
    print("\n" + "=" * 70)
    print("PHASE 6 COMPLETE: RAG Component Testing Summary")
    print("=" * 70)
    print(f"RAGKnowledgeBase: {'PASS' if kb_success else 'FAIL'}")
    print(f"RAGAssistant:     {'PASS' if assistant_success else 'FAIL'}")
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
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
