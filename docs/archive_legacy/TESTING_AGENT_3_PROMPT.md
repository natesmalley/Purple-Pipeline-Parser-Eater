# Testing Agent 3: Knowledge Base & Infrastructure Testing
## Prompt for Haiku Agent

**Priority**: 🟡 MEDIUM
**Effort**: 14-18 hours
**New Test Cases**: 54-66
**Status**: Ready for implementation
**Date**: 2025-11-07

---

## OBJECTIVE

Create comprehensive tests for four ROBUSTNESS components:
1. **rag_assistant.py** - RAG assistant for contextual help (312 lines)
2. **rag_knowledge.py** - Milvus vector database integration (347 lines)
3. **pipeline_validator.py** - Configuration validation (642 lines)
4. **sdl_audit_logger.py** - Security audit logging (340 lines)

These components ensure knowledge base functionality, configuration correctness, and compliance logging work as expected.

---

## COMPONENT 1: rag_assistant.py (312 lines)

### Purpose
Claude-powered RAG Assistant that retrieves relevant knowledge and provides contextual help for pipeline configuration.

### Location
`components/rag_assistant.py`

### Current Test Status
- ⚠️ PARTIAL (70% coverage) - Tested as part of RAG suite
- ❌ NO direct unit tests for assistant logic
- ❌ NO context retrieval accuracy tests
- ❌ NO response generation validation

### What to Test

#### Test Suite 1: Basic Assistant Operations (4-5 tests)
```
test_assistant_initialization() - Setup
  - Input: Assistant config
  - Expected: Creates instance with knowledge DB
  - Validation: instance is not None, ready for queries

test_retrieve_context_for_query() - Knowledge retrieval
  - Input: Query string like "how to transform events?"
  - Expected: Returns relevant context documents
  - Validation: Context is non-empty, relevant

test_generate_response_from_context() - Response generation
  - Input: Query + retrieved context
  - Expected: Claude generates helpful response
  - Mock: Claude API
  - Validation: Response is relevant, actionable

test_format_response_for_output() - Format
  - Input: Raw response from Claude
  - Expected: Formatted for user display
  - Validation: Markdown formatted, easy to read

test_handle_empty_knowledge_base() - Edge case
  - Input: Query with empty knowledge base
  - Expected: Returns graceful message
  - Validation: Doesn't crash, offers help
```

#### Test Suite 2: Context Retrieval Accuracy (5-6 tests)
```
test_retrieve_relevant_context() - Accuracy
  - Setup: Add specific docs to knowledge base
  - Input: Query for that topic
  - Expected: Retrieves correct documents first
  - Validation: Top result matches query

test_retrieve_with_similarity_scoring() - Ranking
  - Input: Query matching multiple docs
  - Expected: Returns sorted by relevance
  - Validation: High similarity first

test_retrieve_handles_synonyms() - Semantic search
  - Setup: Add docs about "transform"
  - Input: Query for "modify" or "change"
  - Expected: Still retrieves relevant docs
  - Validation: Semantic matching works
  - Note: May need embedding model

test_retrieve_with_filters() - Filtered search
  - Input: Query with filter (e.g., "Observo only")
  - Expected: Returns only matching docs
  - Validation: Filter applied correctly

test_retrieve_limit_results() - Pagination
  - Input: Query with limit=5
  - Expected: Returns max 5 results
  - Validation: Exactly 5 (or fewer if available)

test_retrieve_with_offset() - Pagination offset
  - Input: Query with offset=10, limit=5
  - Expected: Returns results 10-15
  - Validation: Skipped first 10 correctly
```

#### Test Suite 3: Response Generation (3-4 tests)
```
test_response_includes_source() - Attribution
  - Input: Response generated from doc
  - Expected: Includes document source
  - Validation: Source document is cited

test_response_includes_examples() - Helpful
  - Input: Query about transformation
  - Expected: Response includes code example
  - Validation: Example is correct, runnable

test_response_includes_alternatives() - Options
  - Input: Query with multiple approaches
  - Expected: Mentions different solutions
  - Validation: Alternatives listed

test_response_too_long() - Length management
  - Input: Query that could generate long response
  - Expected: Truncated to reasonable length
  - Validation: Response has max word count
```

#### Test Suite 4: Error Handling (3-4 tests)
```
test_handle_malformed_query() - Bad input
  - Input: Query with special chars, very long, etc
  - Expected: Handles gracefully
  - Validation: Returns error or default response

test_handle_knowledge_base_error() - DB error
  - Mock: Knowledge base raises error
  - Input: Query
  - Expected: Falls back to default response
  - Validation: Clear error message

test_handle_claude_api_error() - API error
  - Mock: Claude API fails
  - Input: Query
  - Expected: Returns cached response or generic help
  - Validation: Doesn't crash, user gets help

test_timeout_handling() - Slow response
  - Input: Query that times out
  - Expected: Returns timeout message
  - Validation: User knows it timed out
```

### Existing Test Patterns

From `tests/test_rag_components.py` (215+ lines):
```python
@pytest.fixture
def rag_assistant():
    """Create RAG assistant for testing."""
    knowledge = MockKnowledgeBase(...)
    return RagAssistant(knowledge=knowledge)

def test_retrieve_context(rag_assistant):
    """Test context retrieval."""
    context = rag_assistant.retrieve_context("transform events")
    assert len(context) > 0
    assert "transform" in context[0].lower()
```

### Tools & Mocking

**Mock knowledge base**:
```python
@pytest.fixture
def mock_knowledge():
    """Mock knowledge base."""
    mock_kb = MagicMock(spec=RagKnowledge)
    mock_kb.search.return_value = [
        Document(text="Transform events...", source="docs.md"),
    ]
    return mock_kb

def test_retrieve_context(mock_knowledge):
    assistant = RagAssistant(knowledge=mock_knowledge)
    result = assistant.retrieve_context("transform")
    assert len(result) > 0
```

**Mock Claude API**:
```python
@patch('components.rag_assistant.Claude')
def test_generate_response(mock_claude):
    mock_claude.generate.return_value = "Here's how to transform..."

    assistant = RagAssistant()
    response = assistant.generate_response(query="...", context=[...])

    assert "transform" in response
```

### File Locations
- **Component**: `components/rag_assistant.py`
- **Create test file**: `tests/test_rag_assistant_comprehensive.py`
- **Reference**: `tests/test_rag_components.py` (215+ lines)

### Expected Test File Size
- Lines: 200-280
- Test methods: 12-15
- Assertions per test: 2-3

---

## COMPONENT 2: rag_knowledge.py (347 lines)

### Purpose
Milvus vector database integration for storing and retrieving embeddings of knowledge documents.

### Location
`components/rag_knowledge.py`

### Current Test Status
- ⚠️ PARTIAL (70% coverage) - Part of RAG suite
- ❌ NO direct Milvus integration tests
- ❌ NO embedding accuracy tests
- ❌ NO similarity calculation tests

### What to Test

#### Test Suite 1: Database Operations (5-6 tests)
```
test_initialize_milvus_collection() - Create collection
  - Setup: Mock Milvus connection
  - Expected: Creates collection with correct schema
  - Validation: Collection has vector field, metadata fields

test_insert_documents() - Add to DB
  - Input: List of documents
  - Expected: Stored in Milvus
  - Validation: Can be retrieved

test_search_by_vector() - Vector search
  - Input: Query vector
  - Expected: Returns nearest neighbors
  - Validation: Results ranked by distance

test_search_by_text() - Text search
  - Input: Query text
  - Expected: Converts to vector, searches
  - Validation: Results match semantically

test_delete_documents() - Remove
  - Input: Document IDs
  - Expected: Removed from collection
  - Validation: Not found in subsequent searches

test_update_documents() - Modify
  - Input: Updated document content
  - Expected: Milvus collection updated
  - Validation: Old content replaced
```

#### Test Suite 2: Embedding Generation (4-5 tests)
```
test_generate_embedding_from_text() - Embeddings
  - Input: Text document
  - Expected: Returns vector embedding
  - Validation: Vector has correct dimension (384 or configured)

test_embedding_consistency() - Deterministic
  - Input: Same text twice
  - Expected: Identical embeddings
  - Validation: Embeddings are exactly equal

test_embedding_similarity() - Semantic
  - Input: Similar documents
  - Expected: High cosine similarity
  - Validation: Similarity > 0.8

test_embedding_dimension() - Correct size
  - Input: Any document
  - Expected: Embedding has correct dimensions
  - Validation: Vector length matches config

test_batch_embedding_generation() - Efficient
  - Input: 100+ documents
  - Expected: All embedded
  - Validation: Performance acceptable (<5 sec)
```

#### Test Suite 3: Search Accuracy (4-5 tests)
```
test_search_returns_ranked_results() - Ranking
  - Input: Query vector
  - Expected: Results ordered by similarity
  - Validation: Top result most similar

test_search_respects_limit() - Pagination
  - Input: Query with top_k=5
  - Expected: Returns exactly 5 results
  - Validation: No more, no less (unless fewer exist)

test_search_filters() - Conditional search
  - Input: Query with metadata filter
  - Expected: Returns only matching subset
  - Validation: All results match filter

test_search_with_threshold() - Similarity threshold
  - Input: Query requiring similarity > 0.7
  - Expected: Only returns high-similarity results
  - Validation: All results above threshold

test_search_empty_results() - No matches
  - Input: Query with no matches
  - Expected: Returns empty list
  - Validation: Doesn't crash, clear result
```

#### Test Suite 4: Data Integrity (3-4 tests)
```
test_persist_documents_to_disk() - Persistence
  - Input: Documents added to collection
  - Expected: Data survives restart
  - Validation: Can query after reload
  - Note: May need actual Milvus or mock persistence

test_handle_duplicate_documents() - Deduplication
  - Input: Same document added twice
  - Expected: Only stored once (or versioned)
  - Validation: No duplicates in results

test_metadata_preserved() - Metadata retention
  - Input: Document with metadata fields
  - Expected: Metadata stored with embedding
  - Validation: Metadata retrieved with search results

test_vector_dimension_mismatch() - Validation
  - Input: Vector of wrong dimension
  - Expected: Raises error
  - Validation: Error message is clear
```

### Existing Test Patterns

From `tests/test_milvus_connectivity.py` (93 lines):
```python
@pytest.fixture
def mock_milvus():
    """Mock Milvus connection."""
    with patch('components.rag_knowledge.MilvusClient'):
        yield MagicMock()

def test_search_documents(mock_milvus):
    """Test document search."""
    knowledge = RagKnowledge(client=mock_milvus)
    results = knowledge.search("query")
    assert len(results) > 0
```

### Tools & Mocking

**Mock Milvus client**:
```python
@pytest.fixture
def mock_milvus_client():
    """Mock Milvus connection."""
    mock = MagicMock()
    mock.search.return_value = [
        {'vector': [0.1, 0.2, ...], 'distance': 0.95, 'text': '...'},
    ]
    return mock

def test_search(mock_milvus_client):
    knowledge = RagKnowledge(client=mock_milvus_client)
    results = knowledge.search("query")
    assert results[0]['distance'] > 0.9
```

**Mock sentence transformer**:
```python
@patch('components.rag_knowledge.SentenceTransformer')
def test_embedding_generation(mock_transformer):
    mock_transformer.encode.return_value = np.array([0.1, 0.2, ...])

    knowledge = RagKnowledge()
    embedding = knowledge.embed("test document")

    assert len(embedding) == 384
```

### File Locations
- **Component**: `components/rag_knowledge.py`
- **Create test file**: `tests/test_rag_knowledge_comprehensive.py`
- **Reference**: `tests/test_milvus_connectivity.py` (93 lines)

### Expected Test File Size
- Lines: 250-340
- Test methods: 15-18
- Assertions per test: 2-3

---

## COMPONENT 3: pipeline_validator.py (642 lines)

### Purpose
Validates pipeline configurations against schema, checks for required fields, and validates Observo.ai compatibility.

### Location
`components/pipeline_validator.py`

### Current Test Status
- ⚠️ PARTIAL (60% coverage) - Has integration tests
- ❌ NO comprehensive validation tests
- ❌ NO error message clarity tests
- ❌ NO dataplane-specific validation tests

### What to Test

#### Test Suite 1: Configuration Validation (5-6 tests)
```
test_validate_valid_config() - Happy path
  - Input: Valid pipeline configuration
  - Expected: Returns ValidationResult with no errors
  - Validation: is_valid = True, error_count = 0

test_validate_missing_required_field() - Missing field
  - Input: Config missing 'name' field
  - Expected: Returns error about missing 'name'
  - Validation: Error message is clear

test_validate_invalid_field_type() - Type error
  - Input: Config with 'port: "not a number"'
  - Expected: Reports type error
  - Validation: Error indicates expected type

test_validate_invalid_enum_value() - Enum error
  - Input: 'executor: "invalid-executor"'
  - Expected: Reports allowed values
  - Validation: Lists valid options

test_validate_multiple_errors() - Multiple issues
  - Input: Config with 3 errors
  - Expected: Reports all 3 errors
  - Validation: error_count = 3

test_validate_empty_config() - Empty input
  - Input: Empty or None config
  - Expected: Returns errors for required fields
  - Validation: Lists what's missing
```

#### Test Suite 2: Field-Level Validation (4-5 tests)
```
test_validate_string_field() - String validation
  - Input: String field with valid content
  - Expected: Passes validation
  - Validation: No errors for this field

test_validate_numeric_field() - Number validation
  - Input: Numeric field with range
  - Expected: Validates min/max
  - Validation: Out of range detected

test_validate_array_field() - Array validation
  - Input: Array field with items
  - Expected: Validates item types
  - Validation: Type mismatch detected

test_validate_nested_object() - Nested validation
  - Input: Nested config object
  - Expected: Validates nested fields
  - Validation: Errors in nested fields reported

test_validate_format_strings() - Format validation
  - Input: Fields with specific formats (URL, regex, etc)
  - Expected: Validates format
  - Validation: Format violations detected
```

#### Test Suite 3: Business Logic Validation (3-4 tests)
```
test_validate_dataplane_when_enabled() - Conditional
  - Input: Config with dataplane.enabled=true
  - Expected: Validates dataplane config
  - Validation: Checks dataplane specific fields

test_validate_port_not_in_use() - System validation
  - Input: Config with port=8080
  - Expected: Checks port availability
  - Validation: Warns if port in use
  - Note: May need to mock or skip

test_validate_paths_are_absolute() - Path validation
  - Input: Config with relative paths
  - Expected: Reports path issues
  - Validation: Recommends absolute paths

test_validate_secret_not_in_config() - Security
  - Input: Config with secrets in plain text
  - Expected: Warns about secrets
  - Validation: Recommends environment variables
```

#### Test Suite 4: Error Messages (3-4 tests)
```
test_error_message_is_clear() - Clarity
  - Input: Invalid config
  - Expected: Error messages are clear
  - Validation: Specifies what's wrong and why

test_error_includes_location() - Localization
  - Input: Invalid nested field
  - Expected: Error shows path to field
  - Validation: "web_ui.auth_token" not just "auth_token"

test_error_includes_suggestion() - Helpful
  - Input: Invalid value
  - Expected: Suggests correct values
  - Validation: "Use 'development' or 'production'"

test_validation_report_completeness() - Summary
  - Input: Config with errors
  - Expected: Returns full report
  - Validation: Includes all details (count, list, paths)
```

### Existing Test Patterns

From `tests/test_config_validator.py` (284 lines):
```python
@pytest.mark.parametrize("config,expected_errors", [
    (valid_config, 0),
    (config_missing_name, 1),
    (config_invalid_type, 1),
])
def test_validate_config(config, expected_errors):
    validator = PipelineValidator()
    result = validator.validate(config)
    assert result.error_count == expected_errors
```

### Tools & Techniques

**Use parametrize for multiple validation cases**:
```python
@pytest.mark.parametrize("invalid_config,error_field", [
    ({'port': 'not-a-number'}, 'port'),
    ({'name': ''}, 'name'),
    ({'executor': 'invalid'}, 'executor'),
])
def test_validation_errors(invalid_config, error_field):
    validator = PipelineValidator()
    result = validator.validate(invalid_config)
    assert error_field in result.error_message
```

### File Locations
- **Component**: `components/pipeline_validator.py`
- **Create test file**: `tests/test_pipeline_validator_comprehensive.py`
- **Reference**: `tests/test_config_validator.py` (284 lines)

### Expected Test File Size
- Lines: 280-360
- Test methods: 15-18
- Assertions per test: 2-3

---

## COMPONENT 4: sdl_audit_logger.py (340 lines)

### Purpose
SentinelOne Security Data Lake audit logging for compliance and audit trails of all Web UI actions.

### Location
`components/sdl_audit_logger.py`

### Current Test Status
- ⚠️ PARTIAL (60% coverage) - Tested through security middleware
- ❌ NO direct audit logging tests
- ❌ NO compliance format tests
- ❌ NO error recovery tests

### What to Test

#### Test Suite 1: Audit Event Logging (4-5 tests)
```
test_log_user_action() - Log action
  - Input: User action event
  - Expected: Logged to audit trail
  - Validation: Event recorded with timestamp

test_log_includes_required_fields() - Fields
  - Input: User authentication
  - Expected: Log includes user, action, timestamp, IP
  - Validation: All required fields present

test_log_includes_context() - Context
  - Input: Action with context data
  - Expected: Includes relevant context
  - Validation: Can trace action back to source

test_log_maintains_order() - Ordering
  - Input: Multiple events in sequence
  - Expected: Logged in order
  - Validation: Timestamps increasing

test_log_handles_concurrent_events() - Threading
  - Input: Multiple threads logging simultaneously
  - Expected: No lost events, correct ordering
  - Validation: All events logged, no corruption
```

#### Test Suite 2: Compliance Formatting (3-4 tests)
```
test_audit_log_format_is_ocsf() - Schema
  - Input: Audit event
  - Expected: Formatted per OCSF schema
  - Validation: Valid OCSF object

test_audit_log_includes_severity() - Severity
  - Input: Event of different types
  - Expected: Correct severity level assigned
  - Validation: Critical actions have high severity

test_audit_log_includes_category() - Category
  - Input: Different event types
  - Expected: Correct category assigned
  - Validation: Authentication/AuthenticationError, etc

test_sensitive_data_masked() - Privacy
  - Input: Events with passwords, tokens, etc
  - Expected: Sensitive data masked
  - Validation: Passwords shown as '****', tokens truncated
```

#### Test Suite 3: Storage & Delivery (4-5 tests)
```
test_log_persisted_to_storage() - Persistence
  - Input: Audit event
  - Expected: Stored durably
  - Validation: Can be retrieved later

test_log_delivered_to_sdl() - Delivery
  - Input: Audit event
  - Expected: Sent to SentinelOne SDL
  - Mock: SDL API
  - Validation: API called with correct data

test_batch_logging() - Efficiency
  - Input: Multiple events
  - Expected: Batched before sending
  - Validation: Fewer API calls than events

test_retry_on_sdl_failure() - Resilience
  - Input: SDL API temporarily unavailable
  - Expected: Retries delivery
  - Validation: Eventually delivers or queues

test_queue_overflow_handling() - Overflow
  - Input: More events than queue capacity
  - Expected: Oldest discarded or stored to disk
  - Validation: No crashes, clear behavior
```

#### Test Suite 4: Error Handling (3-4 tests)
```
test_handle_malformed_event() - Bad input
  - Input: Event missing required fields
  - Expected: Logs error, doesn't crash
  - Validation: Audit of the audit failure

test_handle_sdl_connection_error() - Network error
  - Input: SDL unreachable
  - Expected: Queues locally, warns
  - Validation: Retries when available

test_handle_encoding_error() - Unicode
  - Input: Event with special characters
  - Expected: Handles encoding
  - Validation: Doesn't crash, characters preserved

test_handle_very_large_event() - Size limit
  - Input: Event data too large
  - Expected: Truncates or rejects
  - Validation: Clear error, doesn't exceed limit
```

### Existing Test Patterns

From `tests/test_security_middleware.py` (263 lines):
```python
@pytest.fixture
def audit_logger():
    """Create audit logger for testing."""
    with patch('components.sdl_audit_logger.SdlClient'):
        logger = SdlAuditLogger()
        yield logger

def test_log_user_action(audit_logger):
    """Test logging user action."""
    audit_logger.log_action(
        user='admin',
        action='create_pipeline',
        resource='pipe-123'
    )

    # Verify logged
    assert audit_logger.logs[-1]['action'] == 'create_pipeline'
```

### Tools & Mocking

**Mock SDL API**:
```python
@patch('components.sdl_audit_logger.SdlClient')
def test_deliver_to_sdl(mock_sdl):
    """Test delivery to SDL."""
    mock_sdl.return_value.send.return_value = True

    logger = SdlAuditLogger()
    logger.log_action(user='test', action='test')

    assert mock_sdl.return_value.send.called
```

**Mock filesystem for persistence**:
```python
@patch('builtins.open', create=True)
def test_persist_audit_log(mock_open):
    """Test persisting log to file."""
    logger = SdlAuditLogger()
    logger.log_action(user='test', action='test')

    # Verify write called
    mock_open.assert_called()
```

### File Locations
- **Component**: `components/sdl_audit_logger.py`
- **Create test file**: `tests/test_sdl_audit_logger_comprehensive.py`
- **Reference**: `tests/test_security_middleware.py` (263 lines)

### Expected Test File Size
- Lines: 250-320
- Test methods: 12-15
- Assertions per test: 2-3

---

## INTEGRATION: All 4 Components

### Test Suite: End-to-End (3-4 tests)
```
test_rag_assistant_with_knowledge() - RAG flow
  - Execute: Knowledge DB -> search -> assistant
  - Expected: Gets relevant context
  - Validation: Response is helpful

test_validator_catches_bad_pipeline_config() - Validation flow
  - Execute: Invalid config -> validator
  - Expected: Returns helpful errors
  - Validation: Errors point to fixes

test_audit_logging_through_system() - Audit flow
  - Execute: User action -> audit logger
  - Expected: Logged, formatted, delivered
  - Validation: In SDL, preserved
```

---

## SUCCESS CRITERIA

### For rag_assistant.py tests:
- [ ] 12-15 test methods
- [ ] 85%+ code coverage
- [ ] Context retrieval tested
- [ ] Response generation validated
- [ ] All error paths covered
- [ ] Tests passing, no linting errors

### For rag_knowledge.py tests:
- [ ] 15-18 test methods
- [ ] 85%+ code coverage
- [ ] Embedding generation tested
- [ ] Search accuracy validated
- [ ] Similarity scoring verified
- [ ] Data integrity tested

### For pipeline_validator.py tests:
- [ ] 15-18 test methods
- [ ] 85%+ code coverage
- [ ] All field types tested
- [ ] Error messages clear
- [ ] Business logic validated
- [ ] Dataplane-specific validation

### For sdl_audit_logger.py tests:
- [ ] 12-15 test methods
- [ ] 85%+ code coverage
- [ ] Event logging verified
- [ ] OCSF compliance tested
- [ ] SDL delivery validated
- [ ] Error recovery tested

### Overall:
- [ ] 54-66 total test methods
- [ ] 85%+ coverage across all 4 components
- [ ] 0 linting errors
- [ ] All error paths tested
- [ ] Clear test documentation
- [ ] Comprehensive integration tests

---

## DELIVERABLES

### File 1: tests/test_rag_assistant_comprehensive.py
- 200-280 lines
- 12-15 test methods
- Covers: Operations, retrieval, generation, errors
- 85%+ coverage

### File 2: tests/test_rag_knowledge_comprehensive.py
- 250-340 lines
- 15-18 test methods
- Covers: DB ops, embeddings, search, integrity
- 85%+ coverage

### File 3: tests/test_pipeline_validator_comprehensive.py
- 280-360 lines
- 15-18 test methods
- Covers: Validation, fields, business logic, errors
- 85%+ coverage

### File 4: tests/test_sdl_audit_logger_comprehensive.py
- 250-320 lines
- 12-15 test methods
- Covers: Logging, compliance, delivery, errors
- 85%+ coverage

---

## ANTI-PATTERNS

❌ **Don't test embedding models directly** - Mock them
❌ **Don't call real Milvus** - Mock the client
❌ **Don't skip error cases** - Every error matters
❌ **Don't ignore security** - Test sensitive data masking
❌ **Don't hardcode test data** - Use fixtures, parametrize
❌ **Don't test compliance blindly** - Verify schema format
❌ **Don't ignore thread safety** - Test concurrent operations

---

## TESTING CHECKLIST

Before submitting:

- [ ] All 4 test files created
- [ ] pytest discovers all tests
- [ ] All tests pass: `pytest -v`
- [ ] Coverage >85% for each component
- [ ] No linting errors: `flake8`
- [ ] Type hints correct: `mypy`
- [ ] All mocks properly configured
- [ ] Error paths tested
- [ ] Integration tests included
- [ ] Docstrings complete

---

**Status**: Ready for Agent 3 implementation
**Estimated Time**: 14-18 hours
**Expected Completion**: ~2-3 days (Haiku agents)
**Final Summary**: All testing complete, 95%+ overall coverage

