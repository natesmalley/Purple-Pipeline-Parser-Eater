# Testing Agent 2: API Integration & Output Management
## Prompt for Haiku Agent

**Priority**: 🔴 HIGH
**Effort**: 14-18 hours
**New Test Cases**: 48-57
**Status**: Ready for implementation
**Date**: 2025-11-07

---

## OBJECTIVE

Create comprehensive tests for three critical INTEGRATION components:
1. **observo_api_client.py** - Primary API client for Observo.ai (875 lines)
2. **parser_output_manager.py** - Output artifact management (508 lines)
3. **s1_docs_processor.py** - SentinelOne documentation processor (654 lines)

These components handle critical data flows: external API integration, output file management, and documentation parsing.

---

## COMPONENT 1: observo_api_client.py (875 lines)

### Purpose
High-level wrapper for Observo.ai API. Handles pipeline CRUD operations, error handling, and retry logic.

### Location
`components/observo_api_client.py`

### Current Test Status
- ⚠️ PARTIAL (60% coverage) - Has some tests but needs expansion
- ⚠️ Many API error scenarios untested
- ❌ NO retry logic validation tests
- ❌ NO timeout/rate limit tests

### What to Test

#### Test Suite 1: Successful Operations (6-7 tests)
```
test_create_pipeline_success() - Create pipeline
  - Setup: Mock Observo API returns 201
  - Input: Valid pipeline config
  - Expected: Returns created pipeline object
  - Validation: Pipeline ID is not None

test_update_pipeline_success() - Update existing
  - Setup: Mock API returns 200
  - Input: Existing pipeline ID + new config
  - Expected: Returns updated pipeline
  - Validation: Changes reflected in return

test_delete_pipeline_success() - Delete pipeline
  - Setup: Mock API returns 204 No Content
  - Input: Valid pipeline ID
  - Expected: Returns True
  - Validation: Correct endpoint called

test_list_pipelines_success() - List all
  - Setup: Mock API returns list of pipelines
  - Input: None
  - Expected: Returns list of Pipeline objects
  - Validation: All pipelines have IDs

test_get_pipeline_success() - Fetch one
  - Setup: Mock API returns specific pipeline
  - Input: Pipeline ID
  - Expected: Returns Pipeline object
  - Validation: ID matches requested

test_validate_pipeline_success() - Validate config
  - Setup: Mock API validation endpoint returns valid
  - Input: Pipeline config
  - Expected: Returns validation result with no errors
  - Validation: error_count == 0

test_deploy_pipeline_success() - Deploy to production
  - Setup: Mock API returns deployment status
  - Input: Pipeline ID
  - Expected: Returns deployment confirmation
  - Validation: Status is 'deployed'
```

#### Test Suite 2: Error Scenarios (7-8 tests)
```
test_api_error_401_unauthorized() - Authentication failure
  - Setup: Mock API returns 401
  - Input: Any request
  - Expected: Raises AuthenticationError
  - Validation: Error message mentions auth

test_api_error_403_forbidden() - Permission denied
  - Setup: Mock API returns 403
  - Input: Request to restricted resource
  - Expected: Raises PermissionError
  - Validation: Error indicates insufficient permissions

test_api_error_404_not_found() - Resource missing
  - Setup: Mock API returns 404
  - Input: Non-existent pipeline ID
  - Expected: Raises NotFoundError
  - Validation: Error mentions missing resource

test_api_error_409_conflict() - Conflict (duplicate, etc)
  - Setup: Mock API returns 409
  - Input: Pipeline name already exists
  - Expected: Raises ConflictError
  - Validation: Error explains conflict

test_api_error_500_server_error() - Server error
  - Setup: Mock API returns 500
  - Input: Any valid request
  - Expected: Raises ServerError
  - Validation: Error indicates server issue

test_api_error_503_unavailable() - Service temporarily down
  - Setup: Mock API returns 503
  - Input: Any request
  - Expected: Raises ServiceUnavailableError
  - Validation: Indicates retry should happen

test_api_error_429_rate_limit() - Rate limiting
  - Setup: Mock API returns 429 with Retry-After header
  - Input: Rapid requests
  - Expected: Raises RateLimitError with backoff info
  - Validation: Includes retry suggestion

test_api_network_error() - Network connectivity
  - Setup: Mock raises ConnectionError
  - Input: Any request
  - Expected: Raises NetworkError
  - Validation: Error indicates connection issue
```

#### Test Suite 3: Retry & Backoff Logic (4-5 tests)
```
test_retry_on_transient_failure() - Automatic retry
  - Setup: Mock fails once with 503, then succeeds
  - Input: Create pipeline request
  - Expected: Returns success on second try
  - Validation: API called twice

test_exponential_backoff() - Increasing delays
  - Setup: Mock fails 3 times, then succeeds
  - Input: Retry-able request
  - Expected: Waits longer between each retry
  - Validation: Total time > sum of individual attempts
  - Note: Use freezegun for time

test_max_retries_exceeded() - Give up
  - Setup: Mock always fails
  - Input: Request with max_retries=3
  - Expected: Raises MaxRetriesError
  - Validation: API called exactly 4 times (initial + 3 retries)

test_no_retry_on_permanent_error() - Don't retry 4XX
  - Setup: Mock returns 401
  - Input: Create pipeline request
  - Expected: Raises error immediately
  - Validation: API called only once
```

#### Test Suite 4: Request Validation (3-4 tests)
```
test_validate_pipeline_config_schema() - Config validation
  - Input: Invalid pipeline config
  - Expected: Raises ValidationError before API call
  - Validation: API not called

test_validate_required_fields() - Required fields
  - Input: Config missing required field
  - Expected: Raises ValidationError
  - Validation: Error lists missing field

test_sanitize_sensitive_data() - Remove secrets
  - Input: Pipeline config with API keys
  - Expected: Keys removed before sending
  - Validation: Config logged without secrets
```

#### Test Suite 5: Request/Response Handling (3-4 tests)
```
test_request_headers_correct() - Proper headers
  - Setup: Mock Observo API
  - Input: Valid request
  - Expected: Correct headers sent (Content-Type, Auth, etc)
  - Validation: Verify mock was called with right headers

test_response_json_parsing() - Parse JSON
  - Setup: Mock returns JSON response
  - Input: API request
  - Expected: Correctly parses response
  - Validation: Response object has correct fields

test_handle_empty_response() - Empty data
  - Setup: Mock returns 200 with empty body
  - Input: Request
  - Expected: Handles gracefully
  - Validation: Returns empty or default object
```

### Existing Test Patterns to Follow

From `tests/test_observo_ingest_client.py` (249 lines - use as reference):
```python
@pytest.fixture
def mock_api_client():
    """Mock the API client."""
    with patch('components.observo_ingest_client.requests.post') as mock_post:
        yield mock_post

def test_ingest_events_success(mock_api_client):
    """Test successful event ingestion."""
    mock_api_client.return_value.status_code = 200
    mock_api_client.return_value.json.return_value = {'success': True}

    client = ObservoIngestClient(api_key='test-key')
    result = client.ingest([event1, event2])

    assert result.success is True
    mock_api_client.assert_called_once()
```

### Tools & Mocking

**Use responses library for HTTP mocking** (better than mock.patch):
```python
import responses

@responses.activate
def test_create_pipeline_success():
    # Mock the API endpoint
    responses.add(
        responses.POST,
        'https://api.observo.ai/v1/pipelines',
        json={'id': 'pipe-123', 'name': 'test'},
        status=201,
    )

    client = ObservoApiClient(api_key='test-key')
    result = client.create_pipeline({...})

    assert result.id == 'pipe-123'
```

**Use freezegun for backoff/retry timing**:
```python
from freezegun import freeze_time

@freeze_time('2025-11-07 10:00:00')
@responses.activate
def test_exponential_backoff():
    # First call fails
    responses.add(responses.POST, 'https://api.observo.ai/v1/pipelines',
                  status=503)
    # Second call succeeds
    responses.add(responses.POST, 'https://api.observo.ai/v1/pipelines',
                  json={'id': 'pipe-123'}, status=201)

    with freeze_time('2025-11-07 10:00:05'):  # 5 seconds later
        client = ObservoApiClient()
        result = client.create_pipeline({...})  # Will retry

    assert result.id == 'pipe-123'
```

### File Locations
- **Component**: `components/observo_api_client.py`
- **Create test file**: `tests/test_observo_api_client_comprehensive.py`
- **Reference existing**: `tests/test_observo_ingest_client.py` (249 lines)

### Expected Test File Size
- Lines: 350-450
- Test methods: 20-25
- Assertions per test: 2-3

---

## COMPONENT 2: parser_output_manager.py (508 lines)

### Purpose
Manages per-parser output directories, saves analysis artifacts (JSON, Lua, etc.), and provides path traversal protection.

### Location
`components/parser_output_manager.py`

### Current Test Status
- ⚠️ PARTIAL (50% coverage) - Indirect testing through pipeline
- ❌ NO direct unit tests
- ❌ NO security tests for path traversal
- ❌ NO file I/O error handling tests

### What to Test

#### Test Suite 1: Directory Management (4-5 tests)
```
test_create_output_directory() - Create dir
  - Input: Parser name
  - Expected: Directory created at correct path
  - Validation: Directory exists, correct permissions
  - Use: tmp_path fixture

test_parser_output_directory_path() - Get directory path
  - Input: Parser ID
  - Expected: Returns correct path
  - Validation: Path is absolute, ends with parser ID

test_create_nested_directories() - Recursive creation
  - Input: Deep parser name path
  - Expected: All parent directories created
  - Validation: Full path exists

test_output_directory_already_exists() - Idempotent
  - Input: Create same directory twice
  - Expected: Second call succeeds (doesn't fail)
  - Validation: No error thrown

test_output_directory_permissions() - Secure permissions
  - Input: Create directory
  - Expected: Permissions are 755 (rwxr-xr-x)
  - Validation: Check with os.stat().st_mode
```

#### Test Suite 2: File Operations (5-6 tests)
```
test_save_analysis_json() - Save analysis
  - Input: Parser ID, ParserAnalysis object
  - Expected: Saves to analysis.json
  - Validation: File exists, content is valid JSON

test_save_lua_transformation() - Save Lua code
  - Input: Parser ID, Lua code string
  - Expected: Saves to transform.lua
  - Validation: File exists, content matches

test_save_pipeline_config() - Save pipeline
  - Input: Parser ID, pipeline dict
  - Expected: Saves to pipeline.json
  - Validation: File is valid JSON, parseable

test_save_validation_report() - Save report
  - Input: Parser ID, validation results
  - Expected: Saves to validation_report.json
  - Validation: Contains all validation fields

test_overwrite_existing_file() - Update
  - Input: Save file that already exists
  - Expected: File is overwritten
  - Validation: New content in file

test_save_with_special_characters() - Handle special chars
  - Input: Parser ID with spaces, quotes, etc
  - Expected: Files saved successfully
  - Validation: Files exist, no errors
```

#### Test Suite 3: File I/O Error Handling (4-5 tests)
```
test_save_to_read_only_directory() - Permission denied
  - Setup: Create read-only directory
  - Input: Try to save file
  - Expected: Raises PermissionError
  - Validation: Error is logged

test_save_to_nonexistent_parent() - Missing parent
  - Input: Parser ID with non-existent parent
  - Expected: Raises error or creates parents
  - Validation: Behavior is documented

test_save_out_of_disk_space() - Disk full
  - Setup: Mock OSError for disk full
  - Input: Save large file
  - Expected: Raises DiskFullError or OSError
  - Validation: Error is clear

test_filename_too_long() - Filename limits
  - Input: Very long parser ID
  - Expected: Handles gracefully (truncate or error)
  - Validation: Predictable behavior

test_concurrent_writes() - Thread safety
  - Input: Multiple threads saving to same directory
  - Expected: No file corruption
  - Validation: All files created successfully
```

#### Test Suite 4: Path Traversal Security (3-4 tests) ⭐ CRITICAL
```
test_path_traversal_parent_directory() - Prevent ../
  - Input: Parser ID containing "../../../"
  - Expected: Rejects or sanitizes
  - Validation: Files not created outside output dir

test_path_traversal_absolute_path() - Prevent /etc/
  - Input: Parser ID starting with "/"
  - Expected: Rejects or sanitizes
  - Validation: Uses relative path only

test_path_traversal_null_bytes() - Prevent null byte injection
  - Input: Parser ID containing null bytes
  - Expected: Rejects safely
  - Validation: No files created

test_symlink_attack() - Prevent symlink traversal
  - Setup: Create symlink to /etc
  - Input: Try to write through symlink
  - Expected: Blocks or warns
  - Validation: No system files modified
```

### Existing Test Patterns

From `tests/test_manifest_store_enhanced.py` (336 lines - good file example):
```python
@pytest.fixture
def temp_store(tmp_path):
    """Create temporary store for testing."""
    store = ManifestStore(str(tmp_path))
    return store

def test_save_manifest(temp_store, tmp_path):
    """Test saving manifest."""
    manifest = {...}
    temp_store.save(manifest)

    saved_file = tmp_path / "manifest.json"
    assert saved_file.exists()
    assert json.loads(saved_file.read_text()) == manifest
```

### Tools & Techniques

**Use tmp_path fixture for file operations**:
```python
def test_save_analysis_json(tmp_path):
    """Test saving analysis to JSON file."""
    manager = ParserOutputManager(base_path=str(tmp_path))
    analysis = ParserAnalysis(...)

    manager.save_analysis('parser-1', analysis)

    analysis_file = tmp_path / 'parser-1' / 'analysis.json'
    assert analysis_file.exists()
    assert json.loads(analysis_file.read_text())['parser_id'] == 'parser-1'
```

**Mock file operations for error testing**:
```python
@patch('builtins.open', side_effect=PermissionError)
def test_save_permission_denied(mock_open):
    """Test handling of permission errors."""
    manager = ParserOutputManager()

    with pytest.raises(PermissionError):
        manager.save_analysis('parser-1', analysis)
```

### File Locations
- **Component**: `components/parser_output_manager.py`
- **Create test file**: `tests/test_parser_output_manager_comprehensive.py`
- **Reference**: `tests/test_manifest_store_enhanced.py` (336 lines)

### Expected Test File Size
- Lines: 250-320
- Test methods: 15-18
- Assertions per test: 2-4

---

## COMPONENT 3: s1_docs_processor.py (654 lines)

### Purpose
Processes SentinelOne documentation (PDF, JSON, YAML, CSV) to extract parser specifications and field mappings.

### Location
`components/s1_docs_processor.py`

### Current Test Status
- ⚠️ PARTIAL (50% coverage) - Basic tests exist
- ❌ NO edge case testing for document parsing
- ❌ NO validation of extracted data
- ❌ NO error recovery tests

### What to Test

#### Test Suite 1: Document Parsing Basics (5-6 tests)
```
test_parse_json_document() - JSON files
  - Input: Valid S1 JSON spec
  - Expected: Extracts parser definition
  - Validation: All fields present

test_parse_yaml_document() - YAML files
  - Input: Valid S1 YAML spec
  - Expected: Parses correctly
  - Validation: Matches JSON parsing

test_parse_csv_document() - CSV field mapping
  - Input: CSV with field mappings
  - Expected: Extracts field names and types
  - Validation: Correct field count

test_parse_pdf_document() - PDF extraction
  - Input: PDF with parser documentation
  - Expected: Extracts text and structure
  - Validation: All text recovered
  - Note: May need to mock PDF library

test_parse_multipart_document() - Multi-format
  - Input: Document with multiple sections
  - Expected: Handles mixed format
  - Validation: All sections extracted

test_parse_empty_document() - Edge case
  - Input: Empty or minimal document
  - Expected: Returns empty or default result
  - Validation: No crash, sensible behavior
```

#### Test Suite 2: Field Extraction (5-6 tests)
```
test_extract_parser_metadata() - Parser info
  - Input: Document with parser metadata
  - Expected: Extracts name, version, author, etc
  - Validation: All metadata fields present

test_extract_field_mappings() - Field definitions
  - Input: Field mapping section
  - Expected: Extracts all field definitions
  - Validation: Field count correct

test_extract_query_language() - Query syntax
  - Input: Query language examples
  - Expected: Identifies query patterns
  - Validation: Patterns match specifications

test_extract_transformation_rules() - Transforms
  - Input: Transformation definitions
  - Expected: Extracts transformation logic
  - Validation: Logic is interpretable

test_extract_enrichment_data() - Enrichment
  - Input: Data enrichment specifications
  - Expected: Extracts enrichment mappings
  - Validation: Mappings are complete

test_handle_missing_fields() - Incomplete data
  - Input: Document missing some fields
  - Expected: Returns partial result gracefully
  - Validation: No crash, clear what's missing
```

#### Test Suite 3: Data Validation (4-5 tests)
```
test_validate_extracted_parser() - Validate output
  - Input: Extracted parser definition
  - Expected: Validates against schema
  - Validation: Passes validation or lists issues

test_validate_field_types() - Type correctness
  - Input: Fields with type definitions
  - Expected: Validates types are standard
  - Validation: Type issues flagged

test_validate_mapping_consistency() - Consistency
  - Input: Field mappings
  - Expected: No duplicate or conflicting mappings
  - Validation: Issues reported

test_validate_unicode_handling() - UTF-8
  - Input: Document with Unicode characters
  - Expected: Correctly handles encoding
  - Validation: Unicode preserved correctly

test_validate_data_completeness() - Completeness
  - Input: Parsed document data
  - Expected: Checks for required fields
  - Validation: Completeness score returned
```

#### Test Suite 4: Error Handling & Recovery (4-5 tests)
```
test_handle_corrupted_document() - Corrupted file
  - Input: Partially corrupted PDF or JSON
  - Expected: Returns error or partial result
  - Validation: Error is descriptive

test_handle_unsupported_format() - Unknown format
  - Input: Document in unsupported format
  - Expected: Raises UnsupportedFormatError
  - Validation: Error message is clear

test_handle_very_large_document() - Performance
  - Input: Very large document (100MB+)
  - Expected: Processes without memory issues
  - Validation: Completes in reasonable time

test_handle_malformed_json() - Invalid JSON
  - Input: Malformed JSON file
  - Expected: Returns parse error
  - Validation: Error indicates problem location

test_handle_encoding_errors() - Wrong encoding
  - Input: Document with wrong encoding
  - Expected: Attempts to detect/convert
  - Validation: Recovers or reports clearly
```

#### Test Suite 5: Output Format (2-3 tests)
```
test_output_is_structured() - Format validation
  - Input: Any valid document
  - Expected: Output is structured object
  - Validation: Can serialize to JSON

test_output_is_idempotent() - Consistency
  - Input: Same document parsed twice
  - Expected: Identical output both times
  - Validation: Results match exactly

test_output_contains_source_reference() - Traceability
  - Input: Extracted data
  - Expected: Output includes document reference
  - Validation: Can trace back to source
```

### Existing Test Patterns

From `tests/test_security_fixes.py` (480 lines - comprehensive example):
```python
@pytest.mark.parametrize("doc_type,expected", [
    ("json", S1Parser),
    ("yaml", S1Parser),
    ("csv", FieldMapping),
])
def test_parse_document_type(doc_type, expected):
    processor = S1DocsProcessor()
    result = processor.parse(f"sample.{doc_type}")
    assert isinstance(result, expected)
```

### Tools & Mocking

**Mock document libraries**:
```python
@patch('components.s1_docs_processor.PyPDF2')
def test_parse_pdf_document(mock_pdf):
    """Test PDF parsing with mocked library."""
    mock_pdf.PdfReader.return_value.pages = [
        MagicMock(extract_text=lambda: "Parser specification...")
    ]

    processor = S1DocsProcessor()
    result = processor.parse('sample.pdf')

    assert result is not None
    mock_pdf.PdfReader.assert_called_once()
```

**Use parametrize for multiple formats**:
```python
@pytest.mark.parametrize("format,content", [
    ("json", '{"parser": "test"}'),
    ("yaml", "parser: test"),
    ("csv", "field,type\nname,string"),
])
def test_parse_formats(format, content):
    processor = S1DocsProcessor()
    result = processor.parse_content(content, format=format)
    assert result.parser_name == "test"
```

### File Locations
- **Component**: `components/s1_docs_processor.py`
- **Create test file**: `tests/test_s1_docs_processor_comprehensive.py`
- **Reference**: `tests/test_security_fixes.py` (480 lines - detailed example)

### Expected Test File Size
- Lines: 350-420
- Test methods: 18-20
- Assertions per test: 2-3

---

## INTEGRATION TESTS (All 3 Components)

### Test Suite: End-to-End Flow (3-4 tests)
```
test_s1_processor_to_output_manager() - Full pipeline
  - Input: S1 document
  - Execute: Parse -> Manager saves -> files created
  - Expected: All files exist with correct content
  - Validation: Files are readable and valid

test_all_output_formats_together() - Complete
  - Input: Complete parser spec
  - Execute: Save JSON, Lua, config, report
  - Expected: All 4 files created
  - Validation: No conflicts, all parseable

test_error_recovery_pipeline() - Resilience
  - Input: Document with some errors
  - Execute: Parse -> save as much as possible
  - Expected: Partial success
  - Validation: Created files are usable
```

### File Location
- `tests/test_api_integration_comprehensive.py` or in each component test file

---

## SUCCESS CRITERIA

### For observo_api_client.py tests:
- [ ] 20-25 test methods
- [ ] 85%+ code coverage
- [ ] All error scenarios tested
- [ ] Retry logic verified
- [ ] All tests passing
- [ ] No linting errors
- [ ] Type checking passes
- [ ] Tests run in <15 seconds

### For parser_output_manager.py tests:
- [ ] 15-18 test methods
- [ ] 85%+ code coverage
- [ ] **Path traversal security verified** ⭐
- [ ] File I/O errors handled
- [ ] All tests passing
- [ ] No linting errors
- [ ] Type checking passes
- [ ] Tests run in <10 seconds

### For s1_docs_processor.py tests:
- [ ] 18-20 test methods
- [ ] 85%+ code coverage
- [ ] All document formats tested
- [ ] Error handling verified
- [ ] All tests passing
- [ ] No linting errors
- [ ] Type checking passes
- [ ] Tests run in <15 seconds

### Overall:
- [ ] 60+ total test methods
- [ ] 85%+ coverage across all 3 components
- [ ] 0 linting errors (flake8, mypy)
- [ ] All error paths tested
- [ ] Security tests included (path traversal)
- [ ] Integration tests included
- [ ] Clear test documentation (docstrings)

---

## DELIVERABLES

### File 1: tests/test_observo_api_client_comprehensive.py
- 350-450 lines
- 20-25 test methods
- Covers: CRUD, errors, retries, validation, requests
- All tests passing, 85%+ coverage

### File 2: tests/test_parser_output_manager_comprehensive.py
- 250-320 lines
- 15-18 test methods
- Covers: Directory mgmt, file ops, error handling, **security**
- All tests passing, 85%+ coverage

### File 3: tests/test_s1_docs_processor_comprehensive.py
- 350-420 lines
- 18-20 test methods
- Covers: Parsing, extraction, validation, error recovery
- All tests passing, 85%+ coverage

---

## ANTI-PATTERNS - DO NOT DO

❌ **Don't call real APIs** - Always mock with responses library
❌ **Don't test third-party libraries** - Mock them
❌ **Don't use sleep() for retries** - Use freezegun
❌ **Don't skip error tests** - Every error path matters
❌ **Don't hardcode file paths** - Use tmp_path fixture
❌ **Don't ignore security** - Test path traversal!
❌ **Don't test Pydantic alone** - Test with context
❌ **Don't write tests without docstrings** - Explain what's tested

---

## RESOURCES

### Component Code
- `components/observo_api_client.py` - 875 lines, primary API
- `components/parser_output_manager.py` - 508 lines, file management
- `components/s1_docs_processor.py` - 654 lines, document parsing

### Existing Test Examples
- `tests/test_observo_ingest_client.py` - 249 lines, API mocking
- `tests/test_manifest_store_enhanced.py` - 336 lines, file I/O
- `tests/test_security_fixes.py` - 480 lines, comprehensive

### Testing Tools
- **responses** - HTTP mocking
- **freezegun** - Time manipulation
- **pytest** - Fixtures, parametrize
- **tmp_path** - Temporary directories
- **unittest.mock** - Patching

---

## TESTING CHECKLIST

Before submitting tests:

- [ ] All 3 test files created
- [ ] pytest discovers all tests: `pytest --collect-only tests/test_observo_api_client_comprehensive.py tests/test_parser_output_manager_comprehensive.py tests/test_s1_docs_processor_comprehensive.py`
- [ ] All tests pass: `pytest -v`
- [ ] Coverage >85% for each component
- [ ] No linting errors: `flake8 tests/test_*_comprehensive.py`
- [ ] Type hints correct: `mypy tests/test_*_comprehensive.py`
- [ ] All mocks properly configured
- [ ] Security tests included (path traversal)
- [ ] Error paths tested (all exceptions)
- [ ] Test names are clear and descriptive
- [ ] Docstrings complete

---

**Status**: Ready for Agent 2 implementation
**Estimated Time**: 14-18 hours
**Expected Completion**: ~2-3 days (Haiku agents)
**Next Agent**: Agent 3 (RAG, Validation, Audit)

