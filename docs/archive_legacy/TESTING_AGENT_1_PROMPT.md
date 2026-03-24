# Testing Agent 1: Core AI & Code Generation
## Prompt for Haiku Agent

**Priority**: 🔴 CRITICAL
**Effort**: 8-12 hours
**New Test Cases**: 27-33
**Status**: Ready for implementation
**Date**: 2025-11-07

---

## OBJECTIVE

Create comprehensive unit tests for the two CORE AI components that power the system:
1. **claude_analyzer.py** - AI-powered semantic parser analysis
2. **lua_generator.py** - LUA code generation engine

These are the HIGHEST PRIORITY components because they directly impact output quality.

---

## COMPONENT 1: claude_analyzer.py (389 lines)

### Purpose
Analyzes parser code semantically using Claude AI to extract insights and generate recommendations.

### Location
`components/claude_analyzer.py`

### Current Test Status
- ⚠️ PARTIAL - Tested indirectly through pipeline tests
- ❌ NO direct unit tests for analyzer logic
- ❌ NO tests for API mocking
- ❌ NO tests for rate limiting behavior

### What to Test

#### Test Suite 1: Basic Analysis (4-5 tests)
```
test_analyze_parser_success() - Happy path
  - Input: Valid parser code with clear patterns
  - Expected: ParserAnalysis object with valid fields
  - Validation: Check all required fields populated

test_analyze_parser_with_comments() - Handle documented code
  - Input: Parser with inline comments
  - Expected: Extracts analysis correctly ignoring comments
  - Validation: Comments don't break analysis

test_analyze_parser_empty_code() - Edge case
  - Input: Empty or whitespace-only code
  - Expected: Handles gracefully (returns empty or default)
  - Validation: No exceptions

test_analyze_parser_very_long_code() - Large input
  - Input: Very long parser (2000+ lines)
  - Expected: Analyzes or returns error appropriately
  - Validation: Handles without timeout

test_analyze_parser_malformed() - Error case
  - Input: Invalid Python syntax
  - Expected: Returns error or None
  - Validation: Error message is helpful
```

#### Test Suite 2: Claude API Integration (4-5 tests)
```
test_claude_api_call_format() - Verify request format
  - Mock: Claude API
  - Input: Parser code
  - Expected: Correct prompt sent to Claude
  - Validation: `mock_claude.analyze.assert_called_with(...)`

test_claude_api_response_parsing() - Parse response
  - Mock: Return specific Claude response
  - Expected: Correctly extracts ParserAnalysis
  - Validation: All fields match Claude response

test_claude_api_timeout() - Handle timeout
  - Mock: Raise TimeoutError
  - Expected: Returns None or empty analysis
  - Validation: No exception propagates

test_claude_api_rate_limit() - Handle 429
  - Mock: Raise RateLimitError on first call, succeed on second
  - Expected: Retry logic works (if implemented)
  - Validation: Eventually succeeds or fails gracefully

test_claude_api_error_500() - Handle server error
  - Mock: Raise RuntimeError (simulating 500)
  - Expected: Returns None or error response
  - Validation: Error is logged, not silently ignored
```

#### Test Suite 3: Rate Limiting & Token Bucket (3-4 tests)
```
test_rate_limit_token_bucket_init() - Token bucket setup
  - Expected: Token bucket initialized with correct values
  - Validation: Check initial token count

test_rate_limit_allows_rapid_calls() - Within limit
  - Input: Multiple calls within rate limit
  - Expected: All succeed without waiting
  - Validation: No sleep/delay calls

test_rate_limit_enforces_quota() - Exceeds limit
  - Input: More calls than rate limit allows
  - Expected: Wait or reject calls
  - Validation: Time between calls is appropriate

test_rate_limit_token_refill() - Time-based refill
  - Mock: time.time() to advance time
  - Expected: Tokens refill after time passes
  - Validation: Correct refill rate
```

### Existing Test Patterns to Follow

From `tests/test_observo_ingest_client.py`:
```python
@pytest.fixture
def mock_client():
    """Setup mock Observo client."""
    with patch('components.observo_ingest_client.ObservoClient'):
        client = ObservoIngestClient(...)
        yield client

def test_something(mock_client):
    result = mock_client.do_thing()
    assert result.is_valid
```

From `tests/test_output_validator.py`:
```python
@pytest.mark.parametrize("event,expected", [
    (valid_event, True),
    (invalid_event, False),
    (minimal_event, True),
])
def test_validate_event(event, expected):
    validator = OutputValidator()
    assert validator.validate(event) == expected
```

### Tools & Mocking

**Use unittest.mock for Claude API**:
```python
from unittest.mock import patch, MagicMock

@patch('components.claude_analyzer.Claude')
def test_analyze_parser_success(mock_claude):
    # Setup
    mock_claude.analyze.return_value = {
        'summary': '...',
        'insights': [...],
    }

    # Execute
    analyzer = ClaudeAnalyzer()
    result = analyzer.analyze(parser_code)

    # Verify
    assert result.summary == '...'
    mock_claude.analyze.assert_called_once()
```

**Use freezegun for time-based tests**:
```python
from freezegun import freeze_time

@freeze_time('2025-11-07 10:00:00')
def test_rate_limit_refill():
    # Time is frozen at 10:00:00
    bucket = TokenBucket(rate=10, capacity=100)

    # Advance time
    with freeze_time('2025-11-07 10:01:00'):
        # Check tokens refilled
```

### File Locations
- **Component**: `components/claude_analyzer.py`
- **Create test file**: `tests/test_claude_analyzer_comprehensive.py`
- **Reference existing tests**: `tests/test_security_fixes.py` (480 lines - good example)

### Expected Test File Size
- Lines: 250-350
- Test classes: 3
- Test methods: 12-15
- Assertions per test: 2-4

### Code Quality Requirements
- ✅ Type hints on all functions: `def test_something() -> None:`
- ✅ Docstrings on all test methods
- ✅ Parametrized tests for multiple cases: `@pytest.mark.parametrize`
- ✅ Fixtures for setup: `@pytest.fixture`
- ✅ NO print statements (use logging if needed)
- ✅ NO hardcoded paths (use tmp_path fixture)
- ✅ NO sleep() calls in tests (use freezegun or mocking)
- ✅ Clean up resources (context managers, fixtures)
- ✅ Descriptive assertion messages

### Linting Rules (NO violations allowed)
```
flake8:
  - Max line length: 100
  - Ignore: E501 (long lines), W503 (line breaks)

pylint:
  - disable: C0111 (missing docstring) - we have them
  - Must pass: undefined-variable, unused-import, syntax-error

mypy:
  - All functions must have type hints
  - Return types required: -> None, -> bool, etc.
```

### How to Run Tests
```bash
# Run just claude_analyzer tests
pytest tests/test_claude_analyzer_comprehensive.py -v

# With coverage
pytest tests/test_claude_analyzer_comprehensive.py --cov=components.claude_analyzer

# Check specific test
pytest tests/test_claude_analyzer_comprehensive.py::test_analyze_parser_success -v
```

---

## COMPONENT 2: lua_generator.py (504 lines)

### Purpose
Generates LUA transformation code from parser analysis for use in Observo.ai pipelines.

### Location
`components/lua_generator.py`

### Current Test Status
- ⚠️ PARTIAL - Tested indirectly through pipeline tests
- ❌ NO direct unit tests for generation logic
- ❌ NO Lua syntax validation tests
- ❌ NO field transformation tests

### What to Test

#### Test Suite 1: Code Generation Basics (4-5 tests)
```
test_generate_lua_simple_mapping() - Basic transformation
  - Input: Simple field mapping (source -> target)
  - Expected: Valid Lua code with mapping logic
  - Validation: Lua code is syntactically correct

test_generate_lua_with_transformation() - Transform function
  - Input: Field with transformation function
  - Expected: Lua code includes transformation
  - Validation: Transformation logic correct

test_generate_lua_multiple_fields() - Multiple mappings
  - Input: 5-10 field mappings
  - Expected: All fields in output Lua code
  - Validation: No duplicates, correct order

test_generate_lua_missing_fields() - Handle missing data
  - Input: Fields that don't exist in source
  - Expected: Lua handles gracefully (returns nil or default)
  - Validation: No crashes, sensible behavior

test_generate_lua_special_chars() - Handle special characters
  - Input: Field names with spaces, quotes, Unicode
  - Expected: Properly escaped in Lua code
  - Validation: Code is still valid
```

#### Test Suite 2: Lua Syntax Validation (4-5 tests)
```
test_generated_lua_is_syntactically_valid() - Parse check
  - Input: Generated Lua code
  - Expected: Can be parsed as valid Lua
  - Validation: Use lua_parser or equivalent
  - Note: May need to mock if no parser library

test_lua_code_has_function_definition() - Function exists
  - Input: Generated code
  - Expected: Contains 'function transform(event)' or similar
  - Validation: Function name and signature correct

test_lua_code_returns_table() - Output format
  - Input: Generated transformation code
  - Expected: Returns a table/object
  - Validation: Contains 'return {...}' statement

test_lua_code_handles_nil_input() - Edge case
  - Input: Null/nil values in event
  - Expected: Lua code handles gracefully
  - Validation: No errors when processing null

test_lua_code_performance() - Execute quickly
  - Input: Run generated code (mocked or actual)
  - Expected: Executes in <100ms
  - Validation: Measure execution time
```

#### Test Suite 3: Field Transformation Logic (3-4 tests)
```
test_transform_string_field() - String handling
  - Input: String field mapping
  - Expected: Lua converts/formats correctly
  - Validation: Output matches expected type

test_transform_numeric_field() - Number conversion
  - Input: Numeric field with unit conversion
  - Expected: Correct math applied
  - Validation: Result is correct number

test_transform_nested_field() - Object hierarchy
  - Input: Nested field path (event.details.severity)
  - Expected: Lua accesses correct hierarchy
  - Validation: Works with nested data

test_generate_performance_recommendations() - Optimization
  - Input: Parser with opportunity for optimization
  - Expected: LuaGenerationResult includes recommendations
  - Validation: Recommendations are actionable
```

### Existing Test Patterns to Follow

From `tests/test_syntax_validation.py`:
```python
@pytest.mark.parametrize("code,is_valid", [
    ("valid code here", True),
    ("invalid >>> code", False),
])
def test_syntax(code, is_valid):
    result = validate_syntax(code)
    assert result == is_valid
```

### Tools & Validation

**Mock LUA parser if needed**:
```python
@patch('components.lua_generator.lua_parser')
def test_lua_syntax_valid(mock_parser):
    mock_parser.parse.return_value = True

    generator = LuaGenerator()
    code = generator.generate(mapping)

    assert generator.is_valid_syntax(code)
    mock_parser.parse.assert_called_once_with(code)
```

**Use string assertions for code validation**:
```python
def test_generate_lua_function_definition():
    generator = LuaGenerator()
    code = generator.generate(simple_mapping)

    # Check function definition exists
    assert 'function transform(event)' in code

    # Check return statement exists
    assert 'return {' in code

    # Check no syntax errors (basic check)
    assert code.count('{') == code.count('}')
    assert code.count('(') == code.count(')')
```

### File Locations
- **Component**: `components/lua_generator.py`
- **Create test file**: `tests/test_lua_generator_comprehensive.py`
- **Reference existing**: `tests/test_syntax_validation.py` (280 lines)

### Expected Test File Size
- Lines: 280-350
- Test classes: 3
- Test methods: 12-15
- Assertions per test: 2-5

### Code Quality Requirements
- ✅ Type hints on all test functions
- ✅ Docstrings explaining test purpose
- ✅ Parametrized tests for multiple cases
- ✅ No magic numbers (use constants/fixtures)
- ✅ Clear assertion messages: `assert X == Y, "Should generate Lua with function definition"`
- ✅ Test one thing per test function
- ✅ Setup/teardown in fixtures, not test bodies

### How to Run Tests
```bash
# Run lua_generator tests
pytest tests/test_lua_generator_comprehensive.py -v

# With coverage
pytest tests/test_lua_generator_comprehensive.py --cov=components.lua_generator

# Run both AI component tests together
pytest tests/test_claude_analyzer_comprehensive.py tests/test_lua_generator_comprehensive.py -v
```

---

## INTEGRATION: Both Components Together

### Test the Pipeline (2-3 tests)
```
test_analyzer_output_feeds_to_generator() - Integration
  - Input: Parser code
  - Execute: analyzer -> generator pipeline
  - Expected: Generates valid Lua code
  - Validation: End-to-end works

test_analysis_insights_improve_code() - Quality check
  - Input: Parser with improvement opportunities
  - Expected: Generated code implements improvements
  - Validation: Code is better with analysis
```

### File Location
- Create in same test files or `tests/test_ai_pipeline_integration.py`
- Keep integration tests separate from unit tests
- Use both mock and some integration elements

---

## SUCCESS CRITERIA

### For claude_analyzer.py tests:
- [ ] 12-15 test methods
- [ ] 85%+ code coverage
- [ ] All tests passing: `pytest --tb=short`
- [ ] No linting errors: `flake8 --max-line-length=100`
- [ ] Type checking passes: `mypy tests/test_claude_analyzer_comprehensive.py`
- [ ] Tests run in <10 seconds total

### For lua_generator.py tests:
- [ ] 12-15 test methods
- [ ] 85%+ code coverage
- [ ] All tests passing
- [ ] No linting errors
- [ ] Type checking passes
- [ ] Tests run in <10 seconds total

### For both components:
- [ ] All edge cases covered (empty, null, very large, special chars)
- [ ] All error paths tested
- [ ] Mocking is clean (no side effects)
- [ ] No flaky tests (no time-dependent failures)
- [ ] Clear test names: `test_[component]_[scenario]_[expected_result]`

---

## ANTI-PATTERNS - DO NOT DO

❌ **Don't test third-party libraries** (Claude SDK)
- We mock Claude, not test the actual Claude SDK

❌ **Don't create integration tests in unit test files**
- Keep unit and integration tests separate

❌ **Don't use sleep() for timing**
- Use freezegun for time-based tests
- Use mocking for delays

❌ **Don't hardcode file paths**
- Use tmp_path fixture for temporary files
- Use config.yaml for paths

❌ **Don't test Pydantic models directly**
- Pydantic validates itself
- Just test our business logic

❌ **Don't skip error cases**
- Every error path needs a test
- Verify error is logged/handled appropriately

---

## DELIVERABLES

### File 1: tests/test_claude_analyzer_comprehensive.py
- 250-350 lines
- 12-15 test methods
- 3 test classes (Basic, API, RateLimiting)
- All tests passing
- 85%+ coverage of claude_analyzer.py

### File 2: tests/test_lua_generator_comprehensive.py
- 280-350 lines
- 12-15 test methods
- 3 test classes (Generation, Syntax, Transformation)
- All tests passing
- 85%+ coverage of lua_generator.py

### File 3: Updated pytest.ini (optional)
- Configure pytest for these tests if needed
- Mark tests with @pytest.mark.ai for filtering

---

## TESTING CHECKLIST

Before considering tests COMPLETE:

- [ ] All test files created
- [ ] pytest discovers all tests: `pytest --collect-only`
- [ ] All tests pass: `pytest -v`
- [ ] Coverage >85%: `pytest --cov=components.claude_analyzer --cov=components.lua_generator --cov-report=term-missing`
- [ ] No linting errors: `flake8 tests/test_claude_analyzer_comprehensive.py tests/test_lua_generator_comprehensive.py`
- [ ] Type hints correct: `mypy tests/`
- [ ] Run with -x flag (stop on first failure): `pytest -x`
- [ ] All mocks are properly cleaned up
- [ ] Test names are clear and descriptive
- [ ] Documentation complete (docstrings)

---

## RESOURCES

### Component Code
- `components/claude_analyzer.py` - Start here to understand structure
- `components/lua_generator.py` - Start here to understand structure

### Existing Test Examples
- `tests/test_security_fixes.py` - 480 lines, good comprehensive example
- `tests/test_observo_ingest_client.py` - 249 lines, good mocking example
- `tests/test_output_validator.py` - 166 lines, good validation example
- `tests/test_syntax_validation.py` - 280 lines, code validation example

### Testing Strategy
- `docs/HONEST_TESTING_STRATEGY.md` - Full testing roadmap
- `docs/TEST_COVERAGE_GAPS_ANALYSIS.md` - Component details

---

## QUESTIONS TO ASK YOURSELF

1. **Did I mock external dependencies?** (Claude API, file I/O)
2. **Did I test error paths?** (timeouts, API errors, invalid input)
3. **Did I use parametrized tests?** (multiple scenarios efficiently)
4. **Are test names descriptive?** (explain what's being tested)
5. **Is coverage >85%?** (check --cov-report)
6. **Do tests run <10 seconds?** (no real API calls, no sleeps)
7. **Are there docstrings?** (explain complex tests)
8. **No linting errors?** (flake8, mypy clean)
9. **Tests independent?** (no cross-test dependencies)
10. **All assertions clear?** (message explains why)

---

**Status**: Ready for Agent 1 implementation
**Estimated Time**: 8-12 hours
**Expected Completion**: ~1-2 days (Haiku agents)
**Next Agent**: Agent 2 (Observo API & Output Management)

