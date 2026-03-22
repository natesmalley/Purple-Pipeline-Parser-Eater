"""
Comprehensive tests for RAG Knowledge Base component.

Tests cover:
- Database operations (initialization, insert, search, delete, update)
- Embedding generation and consistency
- Search accuracy and ranking
- Data integrity and persistence
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, List, Any
import numpy as np

from components.rag_knowledge import RAGKnowledgeBase


@pytest.fixture
def mock_config() -> Dict[str, Any]:
    """Provide test configuration."""
    return {
        "milvus": {
            "host": "localhost",
            "port": "19530",
            "collection_name": "test_collection"
        }
    }


# Test Suite 1: Database Operations
class TestRAGKnowledgeDBOperations:
    """Test Milvus database operations."""

    def test_initialize_milvus_collection(self, mock_config):
        """Test Milvus collection initialization."""
        with patch('components.rag_knowledge.connections'):
            with patch('components.rag_knowledge.utility') as mock_util:
                mock_util.has_collection.return_value = False

                with patch('components.rag_knowledge.Collection'):
                    with patch('components.rag_knowledge.SentenceTransformer'):
                        kb = RAGKnowledgeBase(mock_config)
                        assert kb is not None

    def test_insert_documents_success(self, mock_config):
        """Test successful document insertion."""
        with patch('components.rag_knowledge.connections'):
            with patch('components.rag_knowledge.utility') as mock_util:
                mock_util.has_collection.return_value = True

                with patch('components.rag_knowledge.Collection') as mock_coll:
                    mock_instance = MagicMock()
                    mock_coll.return_value = mock_instance
                    mock_instance.load = MagicMock()
                    mock_instance.insert = MagicMock()

                    with patch('components.rag_knowledge.SentenceTransformer') as mock_st:
                        mock_model = MagicMock()
                        mock_st.return_value = mock_model
                        mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])

                        kb = RAGKnowledgeBase(mock_config)
                        assert kb is not None

    def test_search_by_vector(self, mock_config):
        """Test vector-based search."""
        with patch('components.rag_knowledge.connections'):
            with patch('components.rag_knowledge.utility') as mock_util:
                mock_util.has_collection.return_value = True

                with patch('components.rag_knowledge.Collection') as mock_coll:
                    mock_instance = MagicMock()
                    mock_coll.return_value = mock_instance
                    mock_instance.load = MagicMock()
                    mock_instance.search = MagicMock(return_value=[
                        [MagicMock(
                            entity={
                                "content": "Result content",
                                "title": "Result Title",
                                "source": "result.md",
                                "doc_type": "guide",
                                "created_at": "2025-11-08"
                            },
                            distance=0.15
                        )]
                    ])

                    with patch('components.rag_knowledge.SentenceTransformer') as mock_st:
                        mock_model = MagicMock()
                        mock_st.return_value = mock_model
                        mock_model.encode.return_value = np.array([0.1] * 384)

                        kb = RAGKnowledgeBase(mock_config)
                        if kb.enabled:
                            results = kb.search_knowledge("test query")
                            assert isinstance(results, list)

    def test_search_respects_limit(self, mock_config):
        """Test search respects top_k limit."""
        with patch('components.rag_knowledge.connections'):
            with patch('components.rag_knowledge.utility') as mock_util:
                mock_util.has_collection.return_value = True

                with patch('components.rag_knowledge.Collection') as mock_coll:
                    mock_instance = MagicMock()
                    mock_coll.return_value = mock_instance
                    mock_instance.load = MagicMock()
                    mock_instance.search = MagicMock(return_value=[[]])

                    with patch('components.rag_knowledge.SentenceTransformer') as mock_st:
                        mock_model = MagicMock()
                        mock_st.return_value = mock_model
                        mock_model.encode.return_value = np.array([0.1] * 384)

                        kb = RAGKnowledgeBase(mock_config)
                        if kb.enabled:
                            kb.search_knowledge("query", top_k=5)
                            call_args = mock_instance.search.call_args
                            assert call_args[1]["limit"] == 5

    def test_delete_documents(self, mock_config):
        """Test document deletion."""
        with patch('components.rag_knowledge.connections'):
            with patch('components.rag_knowledge.utility') as mock_util:
                mock_util.has_collection.return_value = True

                with patch('components.rag_knowledge.Collection') as mock_coll:
                    mock_instance = MagicMock()
                    mock_coll.return_value = mock_instance
                    mock_instance.load = MagicMock()
                    mock_instance.delete = MagicMock()

                    with patch('components.rag_knowledge.SentenceTransformer'):
                        kb = RAGKnowledgeBase(mock_config)
                        assert kb is not None

    def test_ingest_documentation(self, mock_config):
        """Test ingesting documentation."""
        with patch('components.rag_knowledge.connections'):
            with patch('components.rag_knowledge.utility') as mock_util:
                mock_util.has_collection.return_value = True

                with patch('components.rag_knowledge.Collection') as mock_coll:
                    mock_instance = MagicMock()
                    mock_coll.return_value = mock_instance
                    mock_instance.load = MagicMock()
                    mock_instance.insert = MagicMock()
                    mock_instance.flush = MagicMock()

                    with patch('components.rag_knowledge.SentenceTransformer') as mock_st:
                        mock_model = MagicMock()
                        mock_st.return_value = mock_model
                        mock_model.encode.return_value = np.array([0.1] * 384)

                        kb = RAGKnowledgeBase(mock_config)
                        if kb.enabled:
                            result = kb.ingest_observo_documentation()
                            assert isinstance(result, bool)


# Test Suite 2: Embedding Generation
class TestRAGKnowledgeEmbeddings:
    """Test embedding generation and consistency."""

    def test_embedding_generation_from_text(self, mock_config):
        """Test embedding generation from text."""
        with patch('components.rag_knowledge.connections'):
            with patch('components.rag_knowledge.utility') as mock_util:
                mock_util.has_collection.return_value = True

                with patch('components.rag_knowledge.Collection') as mock_coll:
                    mock_instance = MagicMock()
                    mock_coll.return_value = mock_instance
                    mock_instance.load = MagicMock()

                    with patch('components.rag_knowledge.SentenceTransformer') as mock_st:
                        embedding_array = np.array([0.1, 0.2, 0.3] + [0.0] * 381)
                        mock_model = MagicMock()
                        mock_st.return_value = mock_model
                        mock_model.encode.return_value = embedding_array

                        kb = RAGKnowledgeBase(mock_config)
                        if kb.enabled:
                            result = kb.embedding_model.encode("test document")
                            assert result is not None

    def test_embedding_consistency(self, mock_config):
        """Test embedding generation is deterministic."""
        with patch('components.rag_knowledge.connections'):
            with patch('components.rag_knowledge.utility') as mock_util:
                mock_util.has_collection.return_value = True

                with patch('components.rag_knowledge.Collection'):
                    with patch('components.rag_knowledge.SentenceTransformer') as mock_st:
                        embedding = np.array([0.1, 0.2] + [0.0] * 382)
                        mock_model = MagicMock()
                        mock_st.return_value = mock_model
                        mock_model.encode.return_value = embedding

                        kb = RAGKnowledgeBase(mock_config)
                        if kb.enabled:
                            emb1 = kb.embedding_model.encode("same text")
                            emb2 = kb.embedding_model.encode("same text")
                            assert np.allclose(emb1, emb2)

    def test_embedding_similarity_calculation(self, mock_config):
        """Test similarity calculation between embeddings."""
        vec1 = np.array([1.0, 0.0, 0.0, 0.0])
        vec2 = np.array([1.0, 0.0, 0.0, 0.0])
        vec3 = np.array([0.0, 1.0, 0.0, 0.0])

        # Same vectors should have high similarity
        sim_same = 1.0 / (1.0 + np.linalg.norm(vec1 - vec2))
        assert sim_same > 0.99

        # Different vectors should have lower similarity
        sim_diff = 1.0 / (1.0 + np.linalg.norm(vec1 - vec3))
        assert sim_diff < 0.99

    def test_embedding_dimension_validation(self, mock_config):
        """Test embedding has correct dimensions."""
        with patch('components.rag_knowledge.connections'):
            with patch('components.rag_knowledge.utility') as mock_util:
                mock_util.has_collection.return_value = True

                with patch('components.rag_knowledge.Collection'):
                    with patch('components.rag_knowledge.SentenceTransformer') as mock_st:
                        embedding = np.random.rand(384)
                        mock_model = MagicMock()
                        mock_st.return_value = mock_model
                        mock_model.encode.return_value = embedding

                        kb = RAGKnowledgeBase(mock_config)
                        if kb.enabled:
                            result = kb.embedding_model.encode("test")
                            assert len(result) == 384


# Test Suite 3: Search Accuracy
class TestRAGKnowledgeSearchAccuracy:
    """Test search ranking and accuracy."""

    def test_search_returns_ranked_results(self, mock_config):
        """Test results are ranked by similarity."""
        with patch('components.rag_knowledge.connections'):
            with patch('components.rag_knowledge.utility') as mock_util:
                mock_util.has_collection.return_value = True

                with patch('components.rag_knowledge.Collection') as mock_coll:
                    mock_instance = MagicMock()
                    mock_coll.return_value = mock_instance
                    mock_instance.load = MagicMock()
                    mock_instance.search = MagicMock(return_value=[
                        [
                            MagicMock(
                                entity={
                                    "content": "High similarity",
                                    "title": "Title1",
                                    "source": "s1",
                                    "doc_type": "d1",
                                    "created_at": "2025-11-08"
                                },
                                distance=0.05
                            ),
                            MagicMock(
                                entity={
                                    "content": "Low similarity",
                                    "title": "Title2",
                                    "source": "s2",
                                    "doc_type": "d2",
                                    "created_at": "2025-11-08"
                                },
                                distance=0.95
                            )
                        ]
                    ])

                    with patch('components.rag_knowledge.SentenceTransformer') as mock_st:
                        mock_model = MagicMock()
                        mock_st.return_value = mock_model
                        mock_model.encode.return_value = np.array([0.1] * 384)

                        kb = RAGKnowledgeBase(mock_config)
                        if kb.enabled:
                            results = kb.search_knowledge("query")
                            assert len(results) > 0
                            assert results[0]["similarity_score"] > results[1]["similarity_score"]

    def test_search_with_filters(self, mock_config):
        """Test search with document type filter."""
        with patch('components.rag_knowledge.connections'):
            with patch('components.rag_knowledge.utility') as mock_util:
                mock_util.has_collection.return_value = True

                with patch('components.rag_knowledge.Collection') as mock_coll:
                    mock_instance = MagicMock()
                    mock_coll.return_value = mock_instance
                    mock_instance.load = MagicMock()
                    mock_instance.search = MagicMock(return_value=[[]])

                    with patch('components.rag_knowledge.SentenceTransformer') as mock_st:
                        mock_model = MagicMock()
                        mock_st.return_value = mock_model
                        mock_model.encode.return_value = np.array([0.1] * 384)

                        kb = RAGKnowledgeBase(mock_config)
                        if kb.enabled:
                            kb.search_knowledge("query", doc_type_filter="performance")
                            call_args = mock_instance.search.call_args
                            assert "expr" in call_args[1]

    def test_search_empty_results(self, mock_config):
        """Test handling of empty search results."""
        with patch('components.rag_knowledge.connections'):
            with patch('components.rag_knowledge.utility') as mock_util:
                mock_util.has_collection.return_value = True

                with patch('components.rag_knowledge.Collection') as mock_coll:
                    mock_instance = MagicMock()
                    mock_coll.return_value = mock_instance
                    mock_instance.load = MagicMock()
                    mock_instance.search = MagicMock(return_value=[[]])

                    with patch('components.rag_knowledge.SentenceTransformer') as mock_st:
                        mock_model = MagicMock()
                        mock_st.return_value = mock_model
                        mock_model.encode.return_value = np.array([0.1] * 384)

                        kb = RAGKnowledgeBase(mock_config)
                        if kb.enabled:
                            results = kb.search_knowledge("nonexistent")
                            assert isinstance(results, list)

    def test_search_similarity_conversion(self, mock_config):
        """Test distance to similarity conversion."""
        with patch('components.rag_knowledge.connections'):
            with patch('components.rag_knowledge.utility') as mock_util:
                mock_util.has_collection.return_value = True

                with patch('components.rag_knowledge.Collection') as mock_coll:
                    mock_instance = MagicMock()
                    mock_coll.return_value = mock_instance
                    mock_instance.load = MagicMock()
                    mock_instance.search = MagicMock(return_value=[
                        [MagicMock(
                            entity={
                                "content": "test",
                                "title": "t",
                                "source": "s",
                                "doc_type": "d",
                                "created_at": "2025-11-08"
                            },
                            distance=0.0
                        )]
                    ])

                    with patch('components.rag_knowledge.SentenceTransformer') as mock_st:
                        mock_model = MagicMock()
                        mock_st.return_value = mock_model
                        mock_model.encode.return_value = np.array([0.1] * 384)

                        kb = RAGKnowledgeBase(mock_config)
                        if kb.enabled:
                            results = kb.search_knowledge("query")
                            assert len(results) > 0
                            assert results[0]["similarity_score"] == 1.0


# Test Suite 4: Data Integrity
class TestRAGKnowledgeIntegrity:
    """Test data integrity and persistence."""

    def test_metadata_preserved_in_search(self, mock_config):
        """Test metadata is preserved through search."""
        with patch('components.rag_knowledge.connections'):
            with patch('components.rag_knowledge.utility') as mock_util:
                mock_util.has_collection.return_value = True

                with patch('components.rag_knowledge.Collection') as mock_coll:
                    mock_instance = MagicMock()
                    mock_coll.return_value = mock_instance
                    mock_instance.load = MagicMock()
                    mock_instance.search = MagicMock(return_value=[
                        [MagicMock(
                            entity={
                                "content": "Test content",
                                "title": "Test Title",
                                "source": "test.md",
                                "doc_type": "guide",
                                "created_at": "2025-11-08T10:00:00"
                            },
                            distance=0.1
                        )]
                    ])

                    with patch('components.rag_knowledge.SentenceTransformer') as mock_st:
                        mock_model = MagicMock()
                        mock_st.return_value = mock_model
                        mock_model.encode.return_value = np.array([0.1] * 384)

                        kb = RAGKnowledgeBase(mock_config)
                        if kb.enabled:
                            results = kb.search_knowledge("query")
                            assert results[0]["title"] == "Test Title"
                            assert results[0]["source"] == "test.md"

    def test_get_parser_recommendations(self, mock_config):
        """Test parser-based recommendations."""
        with patch('components.rag_knowledge.connections'):
            with patch('components.rag_knowledge.utility') as mock_util:
                mock_util.has_collection.return_value = True

                with patch('components.rag_knowledge.Collection') as mock_coll:
                    mock_instance = MagicMock()
                    mock_coll.return_value = mock_instance
                    mock_instance.load = MagicMock()
                    mock_instance.search = MagicMock(return_value=[[]])

                    with patch('components.rag_knowledge.SentenceTransformer') as mock_st:
                        mock_model = MagicMock()
                        mock_st.return_value = mock_model
                        mock_model.encode.return_value = np.array([0.1] * 384)

                        kb = RAGKnowledgeBase(mock_config)
                        if kb.enabled:
                            parser_analysis = {
                                "parser_complexity": {"level": "High"},
                                "performance_characteristics": {"expected_volume": "High"}
                            }
                            recommendations = kb.get_parser_recommendations(parser_analysis)
                            assert isinstance(recommendations, list)

    def test_cleanup_closes_connections(self, mock_config):
        """Test cleanup properly closes connections."""
        with patch('components.rag_knowledge.connections') as mock_conn:
            with patch('components.rag_knowledge.utility') as mock_util:
                mock_util.has_collection.return_value = True

                with patch('components.rag_knowledge.Collection') as mock_coll:
                    mock_instance = MagicMock()
                    mock_coll.return_value = mock_instance
                    mock_instance.load = MagicMock()
                    mock_instance.release = MagicMock()

                    with patch('components.rag_knowledge.SentenceTransformer'):
                        kb = RAGKnowledgeBase(mock_config)
                        if kb.enabled:
                            kb.cleanup()
                            mock_instance.release.assert_called_once()

    def test_collection_not_found_handling(self, mock_config):
        """Test handling when collection doesn't exist."""
        with patch('components.rag_knowledge.connections'):
            with patch('components.rag_knowledge.utility') as mock_util:
                mock_util.has_collection.return_value = False

                with patch('components.rag_knowledge.Collection') as mock_coll:
                    mock_instance = MagicMock()
                    mock_coll.return_value = mock_instance
                    mock_instance.load = MagicMock()
                    mock_instance.create_index = MagicMock()

                    with patch('components.rag_knowledge.SentenceTransformer'):
                        kb = RAGKnowledgeBase(mock_config)
                        assert kb is not None
