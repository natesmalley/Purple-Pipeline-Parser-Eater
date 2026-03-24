# Python Parser Integration Plan - Option 1: Extend Current Application
## Unified Pipeline for YAML and Python Parsers with Local File/Folder Support

**Created:** 2025-11-09
**Status:** DESIGN PHASE
**Estimated Implementation:** 2-3 weeks
**Risk Level:** MEDIUM (extends existing system)

---

## 🎯 OBJECTIVE

Extend the Purple Pipeline Parser Eater to support **Python-based OEM integrations** alongside existing YAML-based AI-SIEM parsers, with unified conversion pipeline and support for **local file/folder input** via both CLI and GUI.

**Goals:**
1. ✅ Support both YAML parsers (GitHub) and Python parsers (local/GitHub)
2. ✅ Unified conversion pipeline (single workflow for both types)
3. ✅ CLI support for local files and folders
4. ✅ GUI support for file upload and folder selection
5. ✅ Backward compatibility (existing functionality unchanged)
6. ✅ Same output: Lua transformations for Observo.ai

---

## 🏗️ UNIFIED ARCHITECTURE

### Enhanced System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    INPUT SOURCES (Enhanced)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────┐  ┌───────────────────┐                 │
│  │  GitHub Scanner    │  │  Local Scanner    │                 │
│  │  (Existing)        │  │  (NEW)            │                 │
│  ├────────────────────┤  ├───────────────────┤                 │
│  │ • YAML parsers     │  │ • Python parsers  │                 │
│  │ • AI-SIEM format   │  │ • Local files     │                 │
│  │ • Remote fetch     │  │ • Local folders   │                 │
│  └────────┬───────────┘  └────────┬──────────┘                 │
│           │                       │                             │
│           └───────────┬───────────┘                             │
│                       ↓                                          │
│           ┌───────────────────────┐                             │
│           │  Unified Parser Queue │                             │
│           │  (Format-Agnostic)    │                             │
│           └───────────┬───────────┘                             │
│                       ↓                                          │
│  ┌────────────────────────────────────────────────────┐         │
│  │         Format Detector & Router                    │         │
│  │  ┌──────────────┐           ┌──────────────┐       │         │
│  │  │ YAML Parser  │           │ Python Parser│       │         │
│  │  │   Handler    │           │   Handler    │       │         │
│  │  └──────┬───────┘           └──────┬───────┘       │         │
│  └─────────┼──────────────────────────┼───────────────┘         │
│            │                          │                          │
│            └────────────┬─────────────┘                          │
│                         ↓                                        │
│           ┌──────────────────────────┐                          │
│           │   Claude AI Analyzer     │                          │
│           │   (Enhanced)             │                          │
│           │  • Analyzes YAML         │                          │
│           │  • Analyzes Python       │                          │
│           │  • Unified analysis      │                          │
│           └──────────┬───────────────┘                          │
│                      ↓                                           │
│           ┌──────────────────────────┐                          │
│           │   Lua Generator          │                          │
│           │   (Enhanced)             │                          │
│           │  • From YAML patterns    │                          │
│           │  • From Python dicts     │                          │
│           │  • Unified output        │                          │
│           └──────────┬───────────────┘                          │
│                      ↓                                           │
│           ┌──────────────────────────┐                          │
│           │   Observo.ai Deployment  │                          │
│           │   (Unchanged)            │                          │
│           └──────────────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔧 COMPONENT DESIGN

### NEW Component 1: LocalParserScanner

**File:** `components/local_parser_scanner.py`

**Purpose:** Scan local filesystem for parsers (Python or YAML)

**Class Definition:**
```python
class LocalParserScanner:
    """
    Scanner for local parser files (Python-based or YAML-based).
    Supports single files or entire directories.
    """

    def __init__(self, config: Dict):
        """
        Initialize local scanner.

        Args:
            config: Configuration with local_path settings
        """
        self.config = config
        self.supported_formats = ['.py', '.yaml', '.yml', '.conf', '.json']

    async def scan_local_path(self, path: str, recursive: bool = True) -> List[Dict]:
        """
        Scan local file or directory for parsers.

        Args:
            path: Local file or directory path
            recursive: Recursively scan subdirectories

        Returns:
            List of parser dictionaries in standardized format

        Raises:
            ValueError: If path doesn't exist
            SecurityError: If path validation fails
        """

    async def scan_python_integration(self, integration_dir: Path) -> Dict:
        """
        Scan Python OEM integration directory.

        Expected structure:
        - handler.py (optional, for context)
        - ocsf_mapping.py (required)
        - mapping.py (optional)
        - sample_logs/ (optional, for testing)

        Returns:
            Parser dict with:
            - parser_id
            - parser_name
            - parser_type: "python_oem"
            - source_path (local)
            - mapping_content (Python dict as string)
            - sample_logs (if available)
            - handler_context (for analysis)
        """

    async def scan_yaml_parser(self, file_path: Path) -> Dict:
        """
        Scan YAML-based parser file.

        Returns:
            Parser dict in same format as GitHubParserScanner
        """

    def detect_parser_type(self, path: Path) -> str:
        """
        Detect parser type from file structure.

        Returns:
            "python_oem" | "yaml_ai_siem" | "unknown"
        """

    async def extract_python_mapping(self, mapping_file: Path) -> Dict:
        """
        Extract OCSF mapping from Python file.

        Parses ocsf_mapping.py and extracts dictionary mappings
        using AST (Abstract Syntax Tree) parsing.

        Returns:
            Dictionary with mapping structure
        """

    async def load_sample_logs(self, integration_dir: Path) -> List[Dict]:
        """
        Load sample logs for testing.

        Looks in sample_logs/ and app_logs/ directories.
        """
```

**Key Features:**
- ✅ Path validation using `utils/security.py:validate_path()`
- ✅ Supports single files or directories
- ✅ Recursive directory scanning
- ✅ Auto-detects parser type (Python vs YAML)
- ✅ Extracts Python dictionaries using AST parsing
- ✅ Loads sample logs for testing
- ✅ Standardized output format (same as GitHub scanner)

---

### NEW Component 2: PythonParserAnalyzer

**File:** `components/python_parser_analyzer.py`

**Purpose:** Analyze Python OCSF mappings for Claude AI processing

**Class Definition:**
```python
class PythonParserAnalyzer:
    """
    Analyzer for Python-based OEM integration parsers.
    Extracts field mappings and prepares for Lua generation.
    """

    def __init__(self, claude_client: AsyncAnthropic):
        self.claude_client = claude_client

    async def analyze_python_mapping(self, parser: Dict) -> Dict:
        """
        Analyze Python OCSF mapping structure.

        Args:
            parser: Parser dict with Python mapping content

        Returns:
            Analysis dict with:
            - mapping_structure: Parsed field mappings
            - event_types: List of event types (if conditional)
            - field_count: Number of field mappings
            - complexity: "simple" | "medium" | "complex"
            - ocsf_classes: OCSF classes used
            - recommended_strategy: Lua generation strategy
        """

    async def extract_field_mappings(self, mapping_content: str) -> Dict:
        """
        Extract field mapping dictionaries from Python code.

        Uses AST parsing to extract dict literals from:
        - Class methods returning dicts
        - Module-level dict variables
        - Function returns

        Returns:
            Structured field mappings
        """

    async def detect_event_types(self, mapping_structure: Dict) -> List[str]:
        """
        Detect if mapping uses event-type based routing.

        Returns:
            List of event type identifiers (e.g., "authentication.login")
        """

    def assess_complexity(self, mapping_structure: Dict) -> str:
        """
        Assess conversion complexity.

        Factors:
        - Number of field mappings
        - Nesting depth
        - Event type diversity
        - Conditional logic

        Returns:
            "simple" | "medium" | "complex"
        """

    async def prepare_for_lua_generation(self, analysis: Dict) -> Dict:
        """
        Prepare analyzed mapping for Lua code generation.

        Structures data for optimal Claude AI prompt:
        - Flattened field paths
        - Event type routing logic
        - OCSF metadata requirements
        - Sample input/output
        """
```

---

### ENHANCED Component 3: UnifiedLuaGenerator

**File:** `components/unified_lua_generator.py` (extends existing `lua_generator.py`)

**Purpose:** Generate Lua from both YAML and Python parsers

**Class Definition:**
```python
class UnifiedLuaGenerator(ClaudeLuaGenerator):
    """
    Enhanced Lua generator supporting both YAML and Python parsers.
    Extends existing ClaudeLuaGenerator with Python support.
    """

    async def generate_lua(self, parser: Dict, analysis: Dict) -> Dict:
        """
        Generate Lua code based on parser type.

        Args:
            parser: Parser dict with type info
            analysis: Analysis results

        Returns:
            Lua code generation result

        Routing:
        - parser_type == "yaml_ai_siem" → generate_from_yaml()
        - parser_type == "python_oem" → generate_from_python()
        """

    async def generate_from_python(
        self,
        parser: Dict,
        analysis: Dict
    ) -> Dict:
        """
        Generate Lua transformation from Python OCSF mapping.

        Process:
        1. Extract field mapping structure
        2. Determine if event-type routing needed
        3. Generate Lua helper functions
        4. Create main transform() function
        5. Add OCSF metadata
        6. Validate syntax

        Returns:
            {
                "lua_code": str,
                "confidence_score": float,
                "strategy": "python_dict_mapping",
                "event_types": List[str],
                "helper_functions": List[str]
            }
        """

    def generate_field_mapping_lua(self, mappings: Dict) -> str:
        """
        Generate Lua code for field-to-field mappings.

        Input: {"source.path.field": "ocsf.target.field"}
        Output: Lua code with get_nested/set_nested logic
        """

    def generate_event_type_router(self, event_types: Dict) -> str:
        """
        Generate Lua event type routing logic.

        Input: {"event_type_1": {...}, "event_type_2": {...}}
        Output: Lua if/elseif/else conditional routing
        """

    def generate_helper_functions(self) -> str:
        """
        Generate standard Lua helper functions.

        Returns:
        - get_nested(table, ...): Access nested fields
        - set_nested(table, value, ...): Set nested fields
        - safe_get(table, key, default): Safe access with default
        - convert_timestamp(ts): Timestamp conversion
        """
```

---

### ENHANCED Component 4: UnifiedParserOrchestrator

**File:** `orchestrator/core.py` (enhanced)

**Purpose:** Orchestrate both parser types through unified pipeline

**Enhanced Workflow:**

```python
async def run_complete_conversion(self):
    """
    Execute complete conversion with support for both parser types.

    Phase 1: Scan Parsers
    - GitHub YAML parsers (existing)
    - Local Python parsers (NEW)
    - Local YAML parsers (NEW)

    Phase 2: Analyze Parsers
    - Route to appropriate analyzer based on type
    - YAML → ClaudeParserAnalyzer (existing)
    - Python → PythonParserAnalyzer (NEW)

    Phase 3: Generate Lua
    - Route to appropriate generator
    - UnifiedLuaGenerator handles both

    Phase 4: Deploy (unchanged)
    Phase 5: Report (unchanged)
    """

    # Phase 1 - Enhanced
    parsers = await self._phase_1_scan_parsers_unified()
    # Returns mixed list of YAML and Python parsers

    # Phase 2 - Enhanced
    analyses = await self._phase_2_analyze_parsers_unified(parsers)
    # Routes each parser to appropriate analyzer

    # Phase 3 - Enhanced
    lua_parsers = await self._phase_3_generate_lua_unified(analyses)
    # Uses UnifiedLuaGenerator

    # Phase 4 & 5 - Unchanged
    # ...
```

---

## 📝 DETAILED IMPLEMENTATION PLAN

### Phase 1: Scanner Enhancement (Week 1)

#### Task 1.1: Create LocalParserScanner

**File:** `components/local_parser_scanner.py`
**Lines:** ~300-400
**Dependencies:** `pathlib`, `ast`, `yaml`, `json`

**Implementation Steps:**

**Step 1: Path Validation**
```python
async def scan_local_path(self, path: str, recursive: bool = True) -> List[Dict]:
    """Scan local file or directory"""
    from utils.security import validate_path, validate_file_path

    # SECURITY: Validate path to prevent traversal
    base_dir = Path.cwd()
    validated_path = validate_path(path, base_dir, allow_absolute=True)

    if validated_path.is_file():
        return await self._scan_single_file(validated_path)
    elif validated_path.is_dir():
        return await self._scan_directory(validated_path, recursive)
    else:
        raise ValueError(f"Path not found: {path}")
```

**Step 2: Directory Scanning**
```python
async def _scan_directory(self, dir_path: Path, recursive: bool) -> List[Dict]:
    """Scan directory for parser integrations"""
    parsers = []

    if recursive:
        # Look for integration directories (contain ocsf_mapping.py or *.conf)
        for subdir in dir_path.iterdir():
            if subdir.is_dir():
                parser = await self._scan_integration_directory(subdir)
                if parser:
                    parsers.append(parser)
    else:
        # Scan only current directory
        parser = await self._scan_integration_directory(dir_path)
        if parser:
            parsers.append(parser)

    return parsers
```

**Step 3: Python Integration Detection**
```python
async def _scan_integration_directory(self, dir_path: Path) -> Optional[Dict]:
    """Detect and scan Python OEM integration"""

    # Check for Python integration markers
    has_ocsf_mapping = (dir_path / "ocsf_mapping.py").exists()
    has_handler = (dir_path / "handler.py").exists()

    if has_ocsf_mapping:
        return await self._scan_python_integration(dir_path)

    # Check for YAML parser
    yaml_files = list(dir_path.glob("*.conf")) + \
                 list(dir_path.glob("*.yaml")) + \
                 list(dir_path.glob("*.yml"))

    if yaml_files:
        return await self._scan_yaml_parser(yaml_files[0])

    return None
```

**Step 4: Python Mapping Extraction**
```python
async def extract_python_mapping(self, mapping_file: Path) -> Dict:
    """
    Extract OCSF mapping from Python file using AST parsing.

    This is the CRITICAL function - it parses Python code to extract dictionaries.
    """
    import ast

    with open(mapping_file, 'r', encoding='utf-8') as f:
        source_code = f.read()

    # Parse Python code
    tree = ast.parse(source_code)

    mappings = {}

    # Find class methods that return dictionaries
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Look for OCSFMapping class
            if node.name == "OCSFMapping":
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        # Extract mapping from method
                        mapping_dict = self._extract_dict_from_function(item)
                        if mapping_dict:
                            mappings[item.name] = mapping_dict

        # Also look for module-level dict assignments
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id.endswith('_mapping') or target.id.endswith('_map'):
                        if isinstance(node.value, ast.Dict):
                            mappings[target.id] = self._ast_dict_to_python_dict(node.value)

    return {
        "mappings": mappings,
        "source_code": source_code,
        "file_path": str(mapping_file)
    }

def _ast_dict_to_python_dict(self, ast_dict: ast.Dict) -> Dict:
    """Convert AST Dict node to Python dict"""
    result = {}
    for key, value in zip(ast_dict.keys, ast_dict.values):
        if isinstance(key, ast.Constant):
            key_str = key.value
            if isinstance(value, ast.Constant):
                result[key_str] = value.value
            elif isinstance(value, ast.Dict):
                result[key_str] = self._ast_dict_to_python_dict(value)
            elif isinstance(value, ast.List):
                result[key_str] = [self._eval_ast_node(item) for item in value.elts]
    return result
```

**Step 5: Sample Log Loading**
```python
async def load_sample_logs(self, integration_dir: Path) -> List[Dict]:
    """Load sample logs for testing Lua conversions"""
    sample_logs = []

    # Look in standard locations
    for sample_dir in ["sample_logs", "app_logs", "examples", "test_data"]:
        sample_path = integration_dir / sample_dir
        if sample_path.exists():
            for json_file in sample_path.glob("*.json"):
                with open(json_file, 'r') as f:
                    try:
                        log_data = json.load(f)
                        sample_logs.append({
                            "file": json_file.name,
                            "data": log_data
                        })
                    except json.JSONDecodeError:
                        continue

    return sample_logs
```

**Standardized Output Format:**
```python
{
    "parser_id": "awscloudtrailmonitoringest",
    "parser_name": "AWS CloudTrail Monitor Ingest",
    "parser_type": "python_oem",  # or "yaml_ai_siem"
    "source_type": "local",  # or "github"
    "source_path": "/full/path/to/integration",
    "config": {
        "mapping_structure": { ... },  # Extracted Python dict
        "event_types": ["default", "admin_login", ...],
        "ocsf_classes": ["4002"],
        "sample_logs": [ ... ]
    },
    "metadata": {
        "file_count": 2,
        "has_handler": True,
        "has_mapping": True,
        "complexity": "simple"  # or "medium" or "complex"
    }
}
```

---

### NEW Component 5: PythonToLuaGenerator

**File:** `components/python_to_lua_generator.py`

**Purpose:** Generate Lua from Python OCSF mappings

**Class Definition:**
```python
class PythonToLuaGenerator:
    """
    Generate Lua transformation code from Python OCSF mappings.
    Converts Python dictionary-based mappings to Lua functions.
    """

    def __init__(self, claude_client: AsyncAnthropic):
        self.claude_client = claude_client
        self.template_registry = ObservoLuaTemplateRegistry()

    async def generate_lua_from_python(
        self,
        parser: Dict,
        analysis: Dict
    ) -> str:
        """
        Generate Lua transformation from Python mapping.

        Uses Claude AI with specialized prompt for Python → Lua conversion.
        """

        prompt = self._build_python_to_lua_prompt(parser, analysis)

        # Call Claude AI
        response = await self.claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0.1,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        lua_code = self._extract_lua_code(response.content[0].text)
        return lua_code

    def _build_python_to_lua_prompt(
        self,
        parser: Dict,
        analysis: Dict
    ) -> str:
        """
        Build Claude AI prompt for Python → Lua conversion.

        Prompt includes:
        - Python OCSF mapping structure
        - Event type routing (if applicable)
        - Sample input logs
        - Expected OCSF output structure
        - Lua helper function templates
        """

        mapping_structure = parser["config"]["mapping_structure"]
        sample_logs = parser["config"].get("sample_logs", [])
        event_types = analysis.get("event_types", [])

        prompt = f"""
You are converting a Python-based SentinelOne SDL integration to Lua transformation code for Observo.ai.

PYTHON OCSF MAPPING:
```python
{json.dumps(mapping_structure, indent=2)}
```

EVENT TYPES DETECTED:
{json.dumps(event_types, indent=2)}

SAMPLE INPUT LOG:
```json
{json.dumps(sample_logs[0]["data"] if sample_logs else {}, indent=2)}
```

REQUIREMENTS:
1. Generate a Lua function named 'transform(event)' that:
   - Takes input event as JSON table
   - Maps fields according to Python dictionary
   - Adds OCSF metadata (class_uid, category_uid, etc.)
   - Returns OCSF-compliant event

2. Include helper functions:
   - get_nested(table, ...): Access nested fields safely
   - set_nested(table, value, ...): Set nested fields
   - safe_get(table, key, default): Safe access with default

3. Handle event type routing if multiple event types:
   - Detect event type from input
   - Route to appropriate mapping function
   - Use if/elseif for conditional logic

4. Add comprehensive error handling:
   - Check for required fields
   - Handle missing data gracefully
   - Log warnings for unexpected structure

5. OCSF Compliance:
   - Include all required OCSF fields
   - Use correct class_uid: {analysis.get('ocsf_classes', [])}
   - Add metadata.version: "1.0.0"
   - Set severity_id appropriately

GENERATE COMPLETE, PRODUCTION-READY LUA CODE.
"""
        return prompt

    def generate_simple_mapping_lua(self, mappings: Dict) -> str:
        """
        Generate Lua for simple field-to-field mappings.

        For parsers without event type routing.
        Creates straightforward field mapping code.
        """
        # Template-based generation for simple cases
        pass

    def generate_event_routed_lua(
        self,
        event_types: Dict[str, Dict]
    ) -> str:
        """
        Generate Lua with event type routing.

        For parsers with multiple event type mappings.
        Creates conditional logic based on event type.
        """
        # Template-based generation with routing
        pass
```

---

### ENHANCED Component 6: CLI with Local Path Support

**File:** `main.py` (enhanced)

**New CLI Arguments:**

```python
def parse_arguments():
    """Enhanced argument parser with local path support"""
    parser = argparse.ArgumentParser(...)

    # ... existing arguments ...

    # NEW: Local parser support
    parser.add_argument(
        "--local-path",
        type=str,
        help="Path to local parser file or directory (Python or YAML)"
    )

    parser.add_argument(
        "--local-recursive",
        action="store_true",
        default=True,
        help="Recursively scan local directories (default: True)"
    )

    parser.add_argument(
        "--parser-format",
        type=str,
        choices=["auto", "python", "yaml"],
        default="auto",
        help="Parser format (auto-detect, python, or yaml)"
    )

    parser.add_argument(
        "--source-type",
        type=str,
        choices=["github", "local", "both"],
        default="github",
        help="Parser source: github, local, or both"
    )

    return parser.parse_args()
```

**Usage Examples:**

```bash
# Scan local Python OEM integrations
python main.py --source-type local \
               --local-path "Python OEM Integration Mapping" \
               --parser-format python

# Scan single Python integration
python main.py --source-type local \
               --local-path "Python OEM Integration Mapping/awscloudtrailmonitoringest"

# Scan local YAML parser
python main.py --source-type local \
               --local-path "/path/to/my-custom-parser.yaml"

# Scan both GitHub and local
python main.py --source-type both \
               --local-path "Python OEM Integration Mapping"

# Auto-detect format
python main.py --local-path "parsers/" --parser-format auto
```

---

### ENHANCED Component 7: GUI with File/Folder Upload

**File:** `components/web_ui/routes.py` (enhanced)

**New GUI Routes:**

```python
@app.route('/api/upload-parser', methods=['POST'])
@auth_decorator
@rate_limit("10 per minute")
def upload_parser_file():
    """
    Upload a single parser file (Python or YAML).

    Accepts:
    - ocsf_mapping.py (Python)
    - handler.py (context)
    - parser.conf (YAML)
    - parser.yaml (YAML)

    Returns:
    - parser_id
    - parser_type (detected)
    - validation_status
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400

    # SECURITY: Validate filename
    from utils.security_utils import validate_filename
    safe_filename = validate_filename(file.filename)

    # SECURITY: Validate file size
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Seek back to start

    if file_size > MAX_UPLOAD_SIZE:
        return jsonify({'error': 'File too large (max 10MB)'}), 400

    # Save to temporary location
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(safe_filename).suffix) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    # Scan the uploaded file
    scanner = LocalParserScanner({})
    parser = await scanner.scan_local_path(tmp_path, recursive=False)

    # Queue for conversion
    await service.conversion_queue.put(parser)

    # Cleanup
    os.unlink(tmp_path)

    return jsonify({
        'success': True,
        'parser_id': parser['parser_id'],
        'parser_type': parser['parser_type'],
        'queued_for_conversion': True
    })


@app.route('/api/upload-integration-folder', methods=['POST'])
@auth_decorator
@rate_limit("5 per minute")
def upload_integration_folder():
    """
    Upload an integration folder as ZIP file.

    Accepts ZIP containing:
    - ocsf_mapping.py
    - handler.py (optional)
    - sample_logs/ (optional)

    Extracts, scans, and queues for conversion.
    """
    if 'folder' not in request.files:
        return jsonify({'error': 'No folder (zip) provided'}), 400

    zip_file = request.files['folder']

    # SECURITY: Validate is ZIP and size
    if not zip_file.filename.endswith('.zip'):
        return jsonify({'error': 'Must be a ZIP file'}), 400

    MAX_ZIP_SIZE = 50 * 1024 * 1024  # 50MB
    zip_file.seek(0, 2)
    if zip_file.tell() > MAX_ZIP_SIZE:
        return jsonify({'error': 'ZIP too large (max 50MB)'}), 400
    zip_file.seek(0)

    # Extract to temporary directory
    import tempfile
    import zipfile

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        zip_path = tmp_path / "upload.zip"

        # Save ZIP
        zip_file.save(zip_path)

        # SECURITY: Validate ZIP contents before extraction
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Check for zip bombs
            if len(zf.namelist()) > 1000:
                return jsonify({'error': 'Too many files in ZIP (max 1000)'}), 400

            # Extract safely
            zf.extractall(tmp_path / "extracted")

        # Scan extracted directory
        scanner = LocalParserScanner({})
        parsers = await scanner.scan_local_path(
            str(tmp_path / "extracted"),
            recursive=True
        )

        # Queue all found parsers
        for parser in parsers:
            await service.conversion_queue.put(parser)

    return jsonify({
        'success': True,
        'parsers_found': len(parsers),
        'parser_ids': [p['parser_id'] for p in parsers],
        'queued_for_conversion': True
    })


@app.route('/api/scan-local-folder', methods=['POST'])
@auth_decorator
@rate_limit("10 per minute")
def scan_local_folder():
    """
    Scan a local folder path on the server.

    Body:
    {
        "folder_path": "/path/to/parsers",
        "recursive": true
    }

    Returns list of found parsers without starting conversion.
    """
    data = request.get_json()
    folder_path = data.get('folder_path')

    if not folder_path:
        return jsonify({'error': 'folder_path required'}), 400

    # SECURITY: Validate path
    from utils.security import validate_directory
    try:
        base_dir = Path.cwd()
        validated_path = validate_directory(
            folder_path,
            base_dir,
            allow_absolute=True
        )
    except SecurityError as e:
        return jsonify({'error': f'Invalid path: {e}'}), 400

    # Scan directory
    scanner = LocalParserScanner({})
    parsers = await scanner.scan_local_path(
        str(validated_path),
        recursive=data.get('recursive', True)
    )

    return jsonify({
        'success': True,
        'folder_path': str(validated_path),
        'parsers_found': len(parsers),
        'parsers': [{
            'parser_id': p['parser_id'],
            'parser_name': p['parser_name'],
            'parser_type': p['parser_type'],
            'complexity': p['metadata'].get('complexity')
        } for p in parsers]
    })


@app.route('/api/convert-local-parsers', methods=['POST'])
@auth_decorator
@rate_limit("5 per minute")
def convert_local_parsers():
    """
    Start conversion of local parsers.

    Body:
    {
        "folder_path": "/path/to/Python OEM Integration Mapping",
        "parser_ids": ["awscloudtrail", "gcpaudit"],  # optional, converts all if not specified
        "recursive": true
    }
    """
    data = request.get_json()
    folder_path = data.get('folder_path')

    # Scan and queue for conversion
    scanner = LocalParserScanner({})
    parsers = await scanner.scan_local_path(folder_path, data.get('recursive', True))

    # Filter by parser_ids if specified
    parser_ids_filter = data.get('parser_ids')
    if parser_ids_filter:
        parsers = [p for p in parsers if p['parser_id'] in parser_ids_filter]

    # Queue all for conversion
    for parser in parsers:
        await service.conversion_queue.put(parser)

    return jsonify({
        'success': True,
        'queued_count': len(parsers),
        'parser_ids': [p['parser_id'] for p in parsers]
    })
```

---

### ENHANCED Component 8: Unified Orchestrator Phase 1

**File:** `orchestrator/core.py` → Enhanced `_phase_1_scan_parsers`

```python
async def _phase_1_scan_parsers_unified(self) -> List[Dict]:
    """
    Phase 1: Scan parsers from all configured sources.

    Supports:
    - GitHub AI-SIEM parsers (existing)
    - Local Python OEM parsers (NEW)
    - Local YAML parsers (NEW)

    Returns unified list of parsers in standardized format.
    """
    phase_start = datetime.now()
    logger.info("\n" + "=" * 70)
    logger.info("PHASE 1: Scanning Parsers (Unified)")
    logger.info("=" * 70)

    all_parsers = []
    config = self.config.get("processing", {})
    source_type = config.get("source_type", "github")  # "github" | "local" | "both"

    # Scan GitHub parsers (existing functionality)
    if source_type in ["github", "both"]:
        logger.info("[GitHub] Scanning SentinelOne AI-SIEM parsers...")
        github_parsers = await self.scanner.scan_parsers()
        logger.info(f"[GitHub] Found {len(github_parsers)} YAML parsers")
        all_parsers.extend(github_parsers)

    # Scan local parsers (NEW functionality)
    if source_type in ["local", "both"]:
        logger.info("[Local] Scanning local parsers...")
        local_scanner = LocalParserScanner(config)

        local_path = config.get("local_parser_path", "Python OEM Integration Mapping")
        recursive = config.get("local_recursive", True)

        local_parsers = await local_scanner.scan_local_path(local_path, recursive)
        logger.info(f"[Local] Found {len(local_parsers)} parsers")
        logger.info(f"[Local] Types: {self._count_by_type(local_parsers)}")
        all_parsers.extend(local_parsers)

    # Statistics
    self.statistics["parsers_scanned"] = len(all_parsers)
    self.statistics["github_parsers"] = sum(1 for p in all_parsers if p.get("source_type") == "github")
    self.statistics["local_parsers"] = sum(1 for p in all_parsers if p.get("source_type") == "local")
    self.statistics["yaml_parsers"] = sum(1 for p in all_parsers if p.get("parser_type") == "yaml_ai_siem")
    self.statistics["python_parsers"] = sum(1 for p in all_parsers if p.get("parser_type") == "python_oem")

    phase_end = datetime.now()
    phase_duration = (phase_end - phase_start).total_seconds()
    self.statistics["phase_timings"]["phase_1_scan"] = phase_duration

    logger.info("=" * 70)
    logger.info(f"[OK] Phase 1 Complete: {len(all_parsers)} total parsers")
    logger.info(f"     GitHub: {self.statistics['github_parsers']}")
    logger.info(f"     Local: {self.statistics['local_parsers']}")
    logger.info(f"     YAML: {self.statistics['yaml_parsers']}")
    logger.info(f"     Python: {self.statistics['python_parsers']}")
    logger.info(f"     Duration: {phase_duration:.1f}s")
    logger.info("=" * 70)

    return all_parsers

def _count_by_type(self, parsers: List[Dict]) -> Dict:
    """Count parsers by type"""
    from collections import Counter
    return dict(Counter(p.get("parser_type") for p in parsers))
```

---

### ENHANCED Component 9: Unified Phase 2 Analyzer

**File:** `orchestrator/core.py` → Enhanced `_phase_2_analyze_parsers`

```python
async def _phase_2_analyze_parsers_unified(self, parsers: List[Dict]) -> List[Dict]:
    """
    Phase 2: Analyze parsers with routing based on type.

    Routes each parser to appropriate analyzer:
    - YAML parsers → ClaudeParserAnalyzer (existing)
    - Python parsers → PythonParserAnalyzer (NEW)

    Returns unified analysis results.
    """
    phase_start = datetime.now()
    logger.info("\n" + "=" * 70)
    logger.info("PHASE 2: Analyzing Parsers (Unified)")
    logger.info("=" * 70)

    analyses = []

    for parser in parsers:
        parser_type = parser.get("parser_type")
        parser_name = parser.get("parser_name")

        try:
            if parser_type == "yaml_ai_siem":
                # Use existing YAML analyzer
                logger.info(f"[YAML] Analyzing {parser_name}...")
                analysis = await self.yaml_analyzer.analyze_parser(parser)

            elif parser_type == "python_oem":
                # Use new Python analyzer
                logger.info(f"[Python] Analyzing {parser_name}...")
                analysis = await self.python_analyzer.analyze_python_mapping(parser)

            else:
                logger.warning(f"[Unknown] Skipping {parser_name} - unknown type: {parser_type}")
                continue

            # Add parser reference
            analysis["parser"] = parser
            analyses.append(analysis)

        except Exception as e:
            logger.error(f"[ERROR] Failed to analyze {parser_name}: {e}")
            self.statistics["errors"].append({
                "parser": parser_name,
                "phase": "analysis",
                "error": str(e)
            })

    logger.info(f"[OK] Analyzed {len(analyses)} parsers successfully")
    return analyses
```

---

### ENHANCED Component 10: Unified Phase 3 Generator

**File:** `orchestrator/core.py` → Enhanced `_phase_3_generate_lua`

```python
async def _phase_3_generate_lua_unified(self, analyses: List[Dict]) -> List[Dict]:
    """
    Phase 3: Generate Lua code with routing based on parser type.

    Routes each analysis to appropriate generator:
    - YAML analyses → generate_from_yaml()
    - Python analyses → generate_from_python()

    Returns unified Lua generation results.
    """
    phase_start = datetime.now()
    logger.info("\n" + "=" * 70)
    logger.info("PHASE 3: Generating Lua Code (Unified)")
    logger.info("=" * 70)

    lua_results = []

    for analysis in analyses:
        parser = analysis.get("parser", {})
        parser_type = parser.get("parser_type")
        parser_name = parser.get("parser_name")

        try:
            if parser_type == "yaml_ai_siem":
                # Use existing YAML → Lua generator
                logger.info(f"[YAML→Lua] Generating for {parser_name}...")
                result = await self.unified_generator.generate_from_yaml(
                    parser,
                    analysis
                )

            elif parser_type == "python_oem":
                # Use new Python → Lua generator
                logger.info(f"[Python→Lua] Generating for {parser_name}...")
                result = await self.unified_generator.generate_from_python(
                    parser,
                    analysis
                )

            else:
                logger.warning(f"[Unknown] Skipping {parser_name}")
                continue

            result["parser"] = parser
            result["analysis"] = analysis
            lua_results.append(result)

            # Validate generated Lua
            validation = await self.validator.validate_lua_syntax(result["lua_code"])
            if not validation["valid"]:
                logger.error(f"[Validation Failed] {parser_name}: {validation['errors']}")

        except Exception as e:
            logger.error(f"[ERROR] Failed to generate Lua for {parser_name}: {e}")
            self.statistics["errors"].append({
                "parser": parser_name,
                "phase": "generation",
                "error": str(e)
            })

    logger.info(f"[OK] Generated Lua for {len(lua_results)} parsers")
    return lua_results
```

---

## 📋 CONFIGURATION ENHANCEMENTS

### config.yaml.example (Enhanced)

```yaml
# Processing Configuration
processing:
  # Parser source: "github", "local", or "both"
  source_type: both

  # GitHub parsers (existing)
  max_parsers: 165
  parser_types:
    - "community"
    - "sentinelone"

  # Local parsers (NEW)
  local_parser_path: "Python OEM Integration Mapping"
  local_recursive: true  # Scan subdirectories
  local_parser_formats:  # Auto-detect if not specified
    - "python"
    - "yaml"

  # Processing behavior
  batch_size: 10
  max_concurrent: 3
  skip_on_error: false  # Continue on parser errors

# Python Parser Settings (NEW)
python_parsers:
  # Enable Python parser support
  enabled: true

  # AST parsing settings
  max_file_size_mb: 10
  parse_timeout_seconds: 30

  # Sample log loading
  load_sample_logs: true
  max_sample_logs: 5

  # Conversion strategy
  use_claude_for_complex: true  # Use Claude for complex parsers
  use_templates_for_simple: true  # Use templates for simple mappings
```

---

## 🎨 GUI ENHANCEMENTS

### Enhanced Web UI

**New Section in Web Dashboard:**

```html
<!-- Local Parser Upload Section -->
<div class="upload-section">
    <h2>Upload Local Parsers</h2>

    <!-- Single File Upload -->
    <div class="upload-single">
        <h3>Upload Single File</h3>
        <form id="single-file-upload">
            <input type="file"
                   id="parser-file"
                   accept=".py,.yaml,.yml,.conf,.json"
                   required>
            <button type="submit">Upload Parser</button>
        </form>
        <p class="help-text">
            Supported: Python (.py), YAML (.yaml, .yml, .conf), JSON (.json)
        </p>
    </div>

    <!-- Folder Upload (ZIP) -->
    <div class="upload-folder">
        <h3>Upload Integration Folder</h3>
        <form id="folder-upload">
            <input type="file"
                   id="folder-zip"
                   accept=".zip"
                   required>
            <button type="submit">Upload ZIP Folder</button>
        </form>
        <p class="help-text">
            ZIP file containing: ocsf_mapping.py, handler.py, sample_logs/
        </p>
    </div>

    <!-- Local Path Scanner -->
    <div class="scan-local">
        <h3>Scan Local Folder</h3>
        <form id="local-scan">
            <input type="text"
                   id="local-path"
                   placeholder="/path/to/parsers"
                   value="Python OEM Integration Mapping"
                   required>
            <label>
                <input type="checkbox" id="recursive" checked>
                Recursive scan
            </label>
            <button type="submit">Scan Folder</button>
        </form>
        <p class="help-text">
            Scan local filesystem for parsers (server-side path)
        </p>
    </div>

    <!-- Upload Status -->
    <div id="upload-status" class="status-box" style="display:none;">
        <h4>Upload Status</h4>
        <div id="upload-results"></div>
    </div>
</div>

<!-- JavaScript for handling uploads -->
<script>
document.getElementById('single-file-upload').addEventListener('submit', async (e) => {
    e.preventDefault();

    const fileInput = document.getElementById('parser-file');
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    const response = await fetch('/api/upload-parser', {
        method: 'POST',
        headers: {
            'X-Auth-Token': AUTH_TOKEN
        },
        body: formData
    });

    const result = await response.json();
    showUploadStatus(result);
});

document.getElementById('folder-upload').addEventListener('submit', async (e) => {
    e.preventDefault();

    const zipInput = document.getElementById('folder-zip');
    const formData = new FormData();
    formData.append('folder', zipInput.files[0]);

    const response = await fetch('/api/upload-integration-folder', {
        method: 'POST',
        headers: {
            'X-Auth-Token': AUTH_TOKEN
        },
        body: formData
    });

    const result = await response.json();
    showUploadStatus(result);
});

document.getElementById('local-scan').addEventListener('submit', async (e) => {
    e.preventDefault();

    const path = document.getElementById('local-path').value;
    const recursive = document.getElementById('recursive').checked;

    const response = await fetch('/api/scan-local-folder', {
        method: 'POST',
        headers: {
            'X-Auth-Token': AUTH_TOKEN,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            folder_path: path,
            recursive: recursive
        })
    });

    const result = await response.json();
    showScanResults(result);
});

function showUploadStatus(result) {
    const statusDiv = document.getElementById('upload-status');
    const resultsDiv = document.getElementById('upload-results');

    if (result.success) {
        resultsDiv.innerHTML = `
            <p class="success">✓ Successfully uploaded</p>
            <p>Parser ID: ${result.parser_id || 'Multiple'}</p>
            <p>Parser Type: ${result.parser_type || 'Various'}</p>
            <p>Parsers Found: ${result.parsers_found || 1}</p>
            <p>Status: Queued for conversion</p>
        `;
    } else {
        resultsDiv.innerHTML = `
            <p class="error">✗ Upload failed</p>
            <p>${result.error}</p>
        `;
    }

    statusDiv.style.display = 'block';
}

function showScanResults(result) {
    const statusDiv = document.getElementById('upload-status');
    const resultsDiv = document.getElementById('upload-results');

    if (result.success) {
        let html = `
            <p class="success">✓ Scan complete</p>
            <p>Folder: ${result.folder_path}</p>
            <p>Parsers Found: ${result.parsers_found}</p>
        `;

        if (result.parsers && result.parsers.length > 0) {
            html += '<h5>Found Parsers:</h5><ul>';
            result.parsers.forEach(p => {
                html += `
                    <li>
                        ${p.parser_name}
                        <span class="badge">${p.parser_type}</span>
                        <span class="badge">${p.complexity}</span>
                    </li>
                `;
            });
            html += '</ul>';
            html += `
                <button onclick="convertParsers('${result.folder_path}')">
                    Convert All Parsers
                </button>
            `;
        }

        resultsDiv.innerHTML = html;
    } else {
        resultsDiv.innerHTML = `
            <p class="error">✗ Scan failed</p>
            <p>${result.error}</p>
        `;
    }

    statusDiv.style.display = 'block';
}

async function convertParsers(folderPath) {
    const response = await fetch('/api/convert-local-parsers', {
        method: 'POST',
        headers: {
            'X-Auth-Token': AUTH_TOKEN,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            folder_path: folderPath,
            recursive: true
        })
    });

    const result = await response.json();
    alert(`Queued ${result.queued_count} parsers for conversion`);
    location.reload();  // Refresh to show pending conversions
}
</script>
```

---

## 🔄 INTEGRATION WORKFLOW

### Complete End-to-End Flow

**Scenario 1: Convert Python OEM Integration via CLI**

```bash
# Convert all Python OEM integrations
python main.py \
    --source-type local \
    --local-path "Python OEM Integration Mapping" \
    --config config.yaml \
    --verbose

# Convert specific integration
python main.py \
    --source-type local \
    --local-path "Python OEM Integration Mapping/awscloudtrailmonitoringest"

# Convert both GitHub and local
python main.py \
    --source-type both \
    --local-path "Python OEM Integration Mapping" \
    --max-parsers 200
```

**What Happens:**
1. LocalParserScanner scans directory
2. Finds 36 Python integrations
3. Extracts OCSF mappings from each
4. Loads sample logs
5. Routes to PythonParserAnalyzer
6. Claude AI analyzes Python mappings
7. PythonToLuaGenerator creates Lua code
8. Pipeline validator validates Lua
9. Deploys to Observo.ai
10. Generates report

---

**Scenario 2: Upload via Web UI**

```
User Actions:
1. Opens Web UI: http://localhost:8080
2. Clicks "Upload Integration Folder"
3. Selects ZIP file: awscloudtrailmonitoringest.zip
4. Uploads file
5. System processes:
   - Extracts ZIP safely
   - Scans for ocsf_mapping.py
   - Detects Python parser type
   - Queues for conversion
6. Shows in "Pending Conversions"
7. User approves/modifies
8. Deploys to Observo.ai
```

---

**Scenario 3: Scan Local Folder via GUI**

```
User Actions:
1. Opens Web UI
2. Enters path: "Python OEM Integration Mapping"
3. Checks "Recursive scan"
4. Clicks "Scan Folder"
5. System shows:
   - 36 parsers found
   - 18 simple, 12 medium, 6 complex
   - Parser names and types
6. User clicks "Convert All"
7. All queued for conversion
8. Process through pipeline
```

---

## 📐 DATA FLOW

### Unified Parser Data Structure

**Standardized Parser Format (Works for Both Types):**

```python
{
    # Common fields
    "parser_id": str,
    "parser_name": str,
    "parser_type": "yaml_ai_siem" | "python_oem",
    "source_type": "github" | "local",
    "source_path": str,

    # Format-specific config
    "config": {
        # For YAML parsers
        "attributes": {...},
        "patterns": {...},
        "formats": [...],

        # For Python parsers
        "mapping_structure": {...},
        "event_types": [...],
        "sample_logs": [...],
        "handler_context": str
    },

    # Common metadata
    "metadata": {
        "complexity": "simple" | "medium" | "complex",
        "file_count": int,
        "line_count": int,
        "ocsf_classes": [...],
        "has_samples": bool
    }
}
```

**This unified structure allows all components to work with both types!**

---

## 🛠️ IMPLEMENTATION PHASES

### PHASE 1: Foundation (Week 1, Days 1-2)

**Deliverables:**
- ✅ `components/local_parser_scanner.py` (300 lines)
  - Path validation
  - Directory traversal
  - Python integration detection
  - YAML file detection
  - Standardized output

**Tasks:**
1. Create LocalParserScanner class
2. Implement path validation (use utils/security.py)
3. Implement directory scanning
4. Detect parser type (Python vs YAML)
5. Extract file contents
6. Unit tests for scanner

**Validation:**
- Scan "Python OEM Integration Mapping" folder
- Successfully detect all 36 integrations
- Extract ocsf_mapping.py from each
- No security issues (path traversal prevented)

---

### PHASE 2: Python Analysis (Week 1, Days 3-5)

**Deliverables:**
- ✅ `components/python_parser_analyzer.py` (250 lines)
  - AST parsing for Python dicts
  - Event type detection
  - Complexity assessment
  - Claude AI integration

- ✅ `components/python_to_lua_generator.py` (400 lines)
  - Claude AI prompts for Python → Lua
  - Field mapping generation
  - Event type routing logic
  - Helper function templates

**Tasks:**
1. Implement AST-based Python dict extraction
2. Create Python → Lua Claude AI prompts
3. Build field mapping converter
4. Generate event type routers
5. Create Lua helper function library
6. Test with 3 sample parsers (simple, medium, complex)

**Validation:**
- Convert awsroute53dnsqueries (simple)
- Convert ciscoduoingestion (medium)
- Convert microsoft (complex)
- Generated Lua passes validation
- OCSF compliance verified

---

### PHASE 3: Pipeline Integration (Week 2, Days 1-3)

**Deliverables:**
- ✅ Enhanced `orchestrator/core.py`
  - Unified Phase 1 scanner
  - Unified Phase 2 analyzer
  - Unified Phase 3 generator

- ✅ Enhanced `components/unified_lua_generator.py`
  - Extends ClaudeLuaGenerator
  - Routes based on parser type
  - Handles both formats

**Tasks:**
1. Modify Phase 1 to call LocalParserScanner
2. Add parser type routing in Phase 2
3. Add generator routing in Phase 3
4. Update statistics tracking
5. Integration testing

**Validation:**
- Convert 5 GitHub YAML parsers (existing functionality)
- Convert 5 local Python parsers (new functionality)
- Both work in same run
- No interference between types
- All deploy successfully

---

### PHASE 4: CLI Enhancements (Week 2, Days 4-5)

**Deliverables:**
- ✅ Enhanced `main.py` with new CLI options
- ✅ Documentation for CLI usage

**Tasks:**
1. Add --source-type argument
2. Add --local-path argument
3. Add --local-recursive argument
4. Add --parser-format argument
5. Update help text
6. Create usage examples

**CLI Options Added:**

```python
# main.py enhancements
parser.add_argument('--source-type',
    choices=['github', 'local', 'both'],
    default='github',
    help='Parser source: github, local, or both')

parser.add_argument('--local-path',
    type=str,
    help='Path to local parser file or directory')

parser.add_argument('--local-recursive',
    action='store_true',
    default=True,
    help='Recursively scan local directories')

parser.add_argument('--parser-format',
    choices=['auto', 'python', 'yaml'],
    default='auto',
    help='Parser format (auto-detect by default)')

parser.add_argument('--include-samples',
    action='store_true',
    help='Load sample logs for testing (Python parsers)')
```

**Validation:**
- Test all new CLI arguments
- Verify path validation works
- Test with various folder structures
- Ensure backward compatibility

---

### PHASE 5: GUI Enhancements (Week 3, Days 1-3)

**Deliverables:**
- ✅ Enhanced `components/web_ui/routes.py`
  - File upload endpoint
  - Folder upload endpoint
  - Local scan endpoint
  - Convert endpoint

- ✅ Enhanced Web UI templates
  - Upload forms
  - Progress indicators
  - Parser list display

**Tasks:**
1. Create upload-parser endpoint
2. Create upload-integration-folder endpoint
3. Create scan-local-folder endpoint
4. Create convert-local-parsers endpoint
5. Add UI components
6. Add JavaScript handlers
7. Add security (file size limits, type validation)

**Security Measures:**
- ✅ File size limits (10MB single file, 50MB ZIP)
- ✅ File type validation (.py, .yaml, .zip only)
- ✅ ZIP bomb prevention (max 1000 files)
- ✅ Path traversal prevention in ZIP extraction
- ✅ Rate limiting (10 uploads/min)
- ✅ Authentication required

**Validation:**
- Test file upload
- Test ZIP upload
- Test local folder scan
- Test conversion trigger
- Security testing (malicious uploads)

---

### PHASE 6: Testing & Documentation (Week 3, Days 4-5)

**Deliverables:**
- ✅ Comprehensive test suite
- ✅ Integration tests
- ✅ User documentation
- ✅ Developer guide

**Tasks:**
1. Unit tests for LocalParserScanner
2. Unit tests for PythonParserAnalyzer
3. Unit tests for PythonToLuaGenerator
4. Integration tests (end-to-end)
5. Security tests
6. Documentation updates

**Test Coverage:**
```python
# tests/test_local_parser_scanner.py
def test_scan_python_integration()
def test_scan_yaml_parser()
def test_detect_parser_type()
def test_extract_python_mapping()
def test_security_path_validation()

# tests/test_python_analyzer.py
def test_analyze_simple_mapping()
def test_analyze_complex_mapping()
def test_detect_event_types()

# tests/test_python_to_lua.py
def test_generate_simple_lua()
def test_generate_event_routed_lua()
def test_lua_syntax_validation()

# tests/integration/test_python_pipeline.py
def test_end_to_end_python_conversion()
def test_mixed_yaml_python_conversion()
```

---

## 📊 DETAILED COMPONENT SPECIFICATIONS

### LocalParserScanner API Contract

**Public Methods:**

```python
class LocalParserScanner:
    async def scan_local_path(
        self,
        path: str,
        recursive: bool = True,
        parser_format: str = "auto"
    ) -> List[Dict]:
        """
        Main entry point for local scanning.

        Args:
            path: Local file or directory path
            recursive: Scan subdirectories
            parser_format: "auto" | "python" | "yaml"

        Returns:
            List of standardized parser dicts
        """

    async def scan_python_integration(
        self,
        integration_dir: Path
    ) -> Dict:
        """
        Scan Python OEM integration.

        Required files:
        - ocsf_mapping.py (must exist)

        Optional files:
        - handler.py (for context)
        - sample_logs/*.json (for testing)
        - mapping.py (additional mappings)
        """

    async def scan_yaml_parser(
        self,
        file_path: Path
    ) -> Dict:
        """
        Scan YAML-based parser file.

        Supports:
        - .conf files
        - .yaml files
        - .yml files
        - .json files (parser config)
        """

    def detect_parser_type(
        self,
        path: Path
    ) -> Tuple[str, str]:
        """
        Detect parser type and format.

        Returns:
            (parser_type, format)

        Examples:
            ("python_oem", "python")
            ("yaml_ai_siem", "yaml")
            ("unknown", "unknown")
        """
```

---

### PythonParserAnalyzer API Contract

**Public Methods:**

```python
class PythonParserAnalyzer:
    async def analyze_python_mapping(
        self,
        parser: Dict
    ) -> Dict:
        """
        Analyze Python OCSF mapping.

        Returns:
            {
                "parser_id": str,
                "parser_type": "python_oem",
                "mapping_analysis": {
                    "field_count": int,
                    "event_types": List[str],
                    "nesting_depth": int,
                    "conditional_logic": bool
                },
                "complexity": "simple" | "medium" | "complex",
                "ocsf_classes": List[str],
                "recommended_strategy": str,
                "lua_generation_hints": {
                    "needs_event_router": bool,
                    "needs_helpers": List[str],
                    "estimated_lua_lines": int
                }
            }
        """

    async def extract_field_mappings(
        self,
        mapping_content: str
    ) -> Dict:
        """
        Extract mappings using AST parsing.

        Returns structured field mapping dictionary.
        """

    def assess_complexity(
        self,
        field_count: int,
        event_type_count: int,
        nesting_depth: int
    ) -> str:
        """
        Assess complexity for Lua generation.

        Rules:
        - Simple: <50 fields, 1 event type, depth <3
        - Medium: 50-150 fields, 2-10 event types, depth <5
        - Complex: >150 fields, >10 event types, depth >=5
        """
```

---

### PythonToLuaGenerator API Contract

**Public Methods:**

```python
class PythonToLuaGenerator:
    async def generate_lua_from_python(
        self,
        parser: Dict,
        analysis: Dict
    ) -> Dict:
        """
        Generate Lua transformation from Python mapping.

        Returns:
            {
                "lua_code": str,
                "confidence_score": float (0.0-1.0),
                "strategy": str,
                "generation_time": float,
                "helper_functions": List[str],
                "event_types_handled": List[str],
                "validation_passed": bool,
                "validation_errors": List[str]
            }
        """

    def generate_field_mapping_lua(
        self,
        mappings: Dict,
        event_type: Optional[str] = None
    ) -> str:
        """
        Generate Lua for field mappings.

        Args:
            mappings: {"source.path": "ocsf.target"}
            event_type: Optional event type context

        Returns:
            Lua code string
        """
```

---

## 🎯 USAGE EXAMPLES

### Example 1: Convert Python OEM Integration via CLI

```bash
# Step 1: Configure
cat >> config.yaml << EOF
processing:
  source_type: local
  local_parser_path: "Python OEM Integration Mapping"
  local_recursive: true

python_parsers:
  enabled: true
  load_sample_logs: true
EOF

# Step 2: Run conversion
python main.py --config config.yaml --verbose

# Output:
# Phase 1: Scanning Parsers (Unified)
# [Local] Found 36 parsers
# [Local] Types: {'python_oem': 36}
#
# Phase 2: Analyzing Parsers (Unified)
# [Python] Analyzing awscloudtrailmonitoringest...
# [Python] Analyzing gcpauditlogsingest...
# ... (36 total)
#
# Phase 3: Generating Lua Code (Unified)
# [Python→Lua] Generating for awscloudtrailmonitoringest...
# ... (36 total)
#
# Phase 4: Deploying Pipelines
# ... (36 deployments)
#
# Phase 5: Generating Report
# ✓ Successfully converted 36 Python OEM integrations
```

---

### Example 2: Mixed GitHub + Local Conversion

```bash
python main.py \
    --source-type both \
    --local-path "Python OEM Integration Mapping" \
    --config config.yaml

# Processes:
# - 165 GitHub YAML parsers (AI-SIEM)
# - 36 local Python parsers (OEM)
# Total: 201 parsers through unified pipeline
```

---

### Example 3: GUI Upload Single Integration

```javascript
// User uploads awscloudtrailmonitoringest.zip

POST /api/upload-integration-folder
Content-Type: multipart/form-data
X-Auth-Token: <token>

Response:
{
  "success": true,
  "parsers_found": 1,
  "parser_ids": ["awscloudtrailmonitoringest"],
  "parser_details": [{
    "parser_id": "awscloudtrailmonitoringest",
    "parser_name": "AWS CloudTrail Monitor Ingest",
    "parser_type": "python_oem",
    "complexity": "simple",
    "field_count": 67,
    "sample_logs_found": 2
  }],
  "queued_for_conversion": true,
  "message": "Integration uploaded and queued. Check 'Pending Conversions' tab."
}

// User sees in Web UI:
// Pending Conversions (1)
// ├─ awscloudtrailmonitoringest (Python OEM)
// │  ├─ Complexity: Simple
// │  ├─ Fields: 67 OCSF mappings
// │  ├─ Sample logs: 2 available
// │  └─ Actions: [Approve] [Reject] [Modify]
```

---

## 🔒 SECURITY CONSIDERATIONS

### Path Validation (Critical)

**All local file operations MUST use validation:**

```python
from utils.security import validate_path, validate_file_path, validate_directory

# For user-provided paths
validated = validate_path(user_path, base_dir, allow_absolute=True)

# Prevents:
- ../../../etc/passwd traversal
- Symlink attacks
- Access outside allowed directories
```

**Applied in:**
- ✅ LocalParserScanner.scan_local_path()
- ✅ Web UI file upload endpoints
- ✅ ZIP extraction (no path traversal in ZIP)
- ✅ CLI --local-path argument

---

### File Upload Security

**Restrictions:**
- ✅ Max file size: 10MB (single file)
- ✅ Max ZIP size: 50MB
- ✅ Max files in ZIP: 1,000
- ✅ Allowed extensions: .py, .yaml, .yml, .conf, .json, .zip
- ✅ Filename sanitization
- ✅ Content-type validation
- ✅ Rate limiting (10 uploads/min)

**ZIP Extraction Security:**
```python
def safe_extract_zip(zip_path: Path, extract_to: Path):
    """Extract ZIP safely preventing path traversal"""
    import zipfile

    with zipfile.ZipFile(zip_path, 'r') as zf:
        # Check for malicious filenames
        for name in zf.namelist():
            # Prevent absolute paths
            if name.startswith('/') or '..' in name:
                raise SecurityError(f"Malicious filename in ZIP: {name}")

            # Prevent path traversal
            full_path = (extract_to / name).resolve()
            if not str(full_path).startswith(str(extract_to.resolve())):
                raise SecurityError(f"Path traversal attempt: {name}")

        # Safe to extract
        zf.extractall(extract_to)
```

---

### AST Parsing Security

**Safe Python Code Parsing:**

```python
def extract_python_mapping(self, code: str) -> Dict:
    """Parse Python code safely without execution"""
    import ast

    # SECURITY: Use AST parsing, NEVER exec() or eval()
    # AST parsing is safe - it only parses, doesn't execute

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"Invalid Python syntax: {e}")

    # Extract dictionaries without executing code
    # This is safe - we're only reading the structure
    mappings = self._walk_ast_for_dicts(tree)

    return mappings
```

**Never use:**
- ❌ `exec()` - Executes arbitrary code
- ❌ `eval()` - Evaluates expressions
- ❌ `compile()` + execution

**Always use:**
- ✅ `ast.parse()` - Safe parsing
- ✅ `ast.walk()` - Safe tree traversal
- ✅ AST node inspection only

---

## 📦 BACKWARD COMPATIBILITY

### Ensuring Existing Functionality Works

**Guaranteed:**
1. ✅ Existing GitHub YAML scanning unchanged
2. ✅ Default behavior: GitHub only (unless --source-type specified)
3. ✅ All existing CLI arguments work
4. ✅ Web UI existing features intact
5. ✅ Phase 4 & 5 (Deploy, Report) unchanged
6. ✅ Configuration backward compatible

**Testing:**
```python
# Test 1: Existing GitHub-only workflow
python main.py --config config.yaml

# Should work exactly as before
# No local scanning unless configured

# Test 2: Existing Web UI
# Navigate to http://localhost:8080
# Existing features all functional
# New upload section is addition, not replacement
```

---

## 🧪 TESTING STRATEGY

### Unit Tests (80+ tests)

**LocalParserScanner (20 tests):**
```python
test_scan_single_python_file()
test_scan_single_yaml_file()
test_scan_directory_recursive()
test_scan_directory_non_recursive()
test_detect_python_integration()
test_detect_yaml_parser()
test_extract_simple_python_mapping()
test_extract_complex_python_mapping()
test_extract_event_typed_mapping()
test_load_sample_logs()
test_path_validation_prevents_traversal()
test_invalid_path_raises_error()
test_empty_directory_returns_empty()
test_mixed_directory_detects_both()
# ... 6 more
```

**PythonParserAnalyzer (15 tests):**
```python
test_analyze_simple_mapping()
test_analyze_medium_mapping()
test_analyze_complex_mapping()
test_detect_single_event_type()
test_detect_multiple_event_types()
test_complexity_assessment_simple()
test_complexity_assessment_medium()
test_complexity_assessment_complex()
test_ast_parsing_handles_errors()
# ... 6 more
```

**PythonToLuaGenerator (25 tests):**
```python
test_generate_simple_field_mapping()
test_generate_nested_field_mapping()
test_generate_event_router()
test_generate_helper_functions()
test_validate_generated_lua()
test_ocsf_compliance()
test_handle_missing_fields()
test_timestamp_conversion()
# ... 17 more
```

**Integration Tests (10 tests):**
```python
test_end_to_end_python_conversion()
test_end_to_end_yaml_conversion()
test_mixed_python_yaml_batch()
test_cli_local_path()
test_gui_file_upload()
test_gui_folder_scan()
# ... 4 more
```

**Security Tests (10 tests):**
```python
test_path_traversal_prevention()
test_zip_bomb_prevention()
test_malicious_filename_rejection()
test_file_size_limits()
test_ast_parsing_safe()
# ... 5 more
```

---

## 📖 DOCUMENTATION UPDATES

### User Documentation

**New Sections:**

**README.md:**
- Add "Local Parser Support" section
- Document CLI --local-path option
- Document GUI upload feature
- Add Python parser conversion examples

**docs/SETUP_GUIDE.md:**
- How to prepare Python OEM integrations
- Directory structure requirements
- Sample log preparation

**docs/USAGE_GUIDE.md (NEW):**
- Converting Python OEM integrations
- CLI examples for local files
- GUI upload walkthrough
- Troubleshooting common issues

### Developer Documentation

**docs/development/PYTHON_PARSER_ARCHITECTURE.md (NEW):**
- Component architecture
- Data flow diagrams
- API contracts
- Extension points

**docs/development/ADDING_PARSER_TYPES.md (NEW):**
- How to add support for new parser formats
- Scanner interface
- Analyzer interface
- Generator interface

---

## 🎯 SUCCESS CRITERIA

### Phase 1 Success:
- [ ] LocalParserScanner created
- [ ] Scans "Python OEM Integration Mapping" successfully
- [ ] Detects all 36 integrations
- [ ] Extracts OCSF mappings
- [ ] No security issues
- [ ] All tests passing

### Phase 2 Success:
- [ ] PythonParserAnalyzer created
- [ ] Analyzes simple, medium, complex parsers
- [ ] Detects event types correctly
- [ ] Assesses complexity accurately
- [ ] PythonToLuaGenerator created
- [ ] Generates valid Lua from Python mappings
- [ ] 3 test conversions successful

### Phase 3 Success:
- [ ] Unified pipeline working
- [ ] Both YAML and Python parsers process together
- [ ] No interference between types
- [ ] All phases route correctly
- [ ] Statistics track both types

### Phase 4 Success:
- [ ] CLI accepts --local-path
- [ ] CLI accepts --source-type
- [ ] All argument combinations work
- [ ] Backward compatible (existing args work)
- [ ] Help text updated

### Phase 5 Success:
- [ ] Web UI has upload forms
- [ ] File upload works
- [ ] ZIP folder upload works
- [ ] Local folder scan works
- [ ] Security measures in place
- [ ] UI is intuitive

### Phase 6 Success:
- [ ] 80+ unit tests passing
- [ ] 10+ integration tests passing
- [ ] Security tests passing
- [ ] Documentation complete
- [ ] Code review passed

### Overall Success:
- [ ] All 6 phases complete
- [ ] Can convert 36 Python OEM integrations
- [ ] Can convert 165 GitHub YAML parsers
- [ ] Both work in same pipeline
- [ ] CLI and GUI support both types
- [ ] Zero security issues
- [ ] Zero regressions
- [ ] Production ready

---

## 📅 TIMELINE

### 3-Week Implementation Schedule

**Week 1:**
- Days 1-2: LocalParserScanner (foundation)
- Days 3-5: Python analyzer and Lua generator
- Milestone: Can convert 3 test parsers

**Week 2:**
- Days 1-3: Pipeline integration (unified orchestrator)
- Days 4-5: CLI enhancements
- Milestone: CLI works end-to-end

**Week 3:**
- Days 1-3: GUI enhancements
- Days 4-5: Testing, documentation, polish
- Milestone: Production ready

**Total: 15 working days**

---

## 💰 EFFORT ESTIMATION

### Development Effort

| Component | Lines of Code | Days | Developer |
|-----------|---------------|------|-----------|
| LocalParserScanner | 300 | 2 | 1 |
| PythonParserAnalyzer | 250 | 1.5 | 1 |
| PythonToLuaGenerator | 400 | 2.5 | 1 |
| Pipeline Integration | 200 | 2 | 1 |
| CLI Enhancements | 100 | 1 | 1 |
| GUI Enhancements | 300 | 2 | 1 |
| Testing | 500 | 2 | 1 |
| Documentation | - | 2 | 1 |
| **TOTAL** | **~2,050** | **15** | **1** |

**With 2 developers: 7-8 days**
**With focused effort: 2-3 weeks**

---

## 🚀 QUICK START (Proof of Concept)

### Convert Your First Python Parser TODAY

**Without building anything, test the concept:**

```bash
# Step 1: Pick a simple parser
cd "Python OEM Integration Mapping/awsroute53dnsqueries"

# Step 2: Read the mapping
cat mapping.py

# Step 3: Ask Claude to convert
# (Use the Claude API or Claude Code)

# Prompt:
# "Convert this Python OCSF mapping to Lua:
# [paste mapping.py]
#
# Generate a transform(event) function that maps fields
# from AWS Route53 logs to OCSF format."

# Step 4: Test generated Lua
# Save to test.lua
# Validate with pipeline_validator.py

# Step 5: Deploy
# Add to Observo.ai manually or via API
```

**This proves the concept works before building the automation!**

---

## 🎓 TRAINING & ONBOARDING

### For Developers

**Topics to Cover:**
1. Unified parser architecture
2. LocalParserScanner usage
3. Python AST parsing basics
4. Lua generation strategies
5. Testing local parsers
6. Security considerations

**Resources:**
- Architecture diagrams
- Code walkthroughs
- Example conversions
- Test examples

### For Users

**Topics to Cover:**
1. How to upload Python integrations
2. How to use local folder scanning
3. Understanding conversion results
4. Troubleshooting failed conversions

**Resources:**
- User guide
- Video walkthrough (optional)
- FAQ document
- Example uploads

---

## 📊 METRICS & MONITORING

### New Metrics to Track

**Conversion Metrics:**
- `python_parsers_scanned`: Counter
- `python_parsers_converted`: Counter
- `python_conversion_failures`: Counter
- `local_scans_performed`: Counter
- `files_uploaded`: Counter
- `folders_uploaded`: Counter

**Performance Metrics:**
- `local_scan_duration_seconds`: Histogram
- `python_analysis_duration_seconds`: Histogram
- `python_lua_generation_duration_seconds`: Histogram
- `ast_parsing_duration_seconds`: Histogram

**Quality Metrics:**
- `python_lua_validation_pass_rate`: Gauge
- `python_complexity_distribution`: Counter (simple/medium/complex)
- `event_type_diversity`: Histogram

---

## 🔍 RISK MITIGATION

### Identified Risks & Mitigations

**Risk 1: AST Parsing Failures**
- **Mitigation:** Robust error handling, fallback to text analysis
- **Impact:** Low - can still extract mappings manually

**Risk 2: Complex Logic Lost in Translation**
- **Mitigation:** Start with simple parsers, build confidence
- **Impact:** Medium - may need manual review for complex parsers

**Risk 3: Path Traversal Vulnerabilities**
- **Mitigation:** Comprehensive path validation using utils/security.py
- **Impact:** High if not mitigated - CRITICAL to implement correctly

**Risk 4: ZIP Bomb Attacks**
- **Mitigation:** File count limits, size limits, extraction validation
- **Impact:** Medium - DoS potential

**Risk 5: Performance with Large Folders**
- **Mitigation:** Async scanning, progress indicators, timeouts
- **Impact:** Low - user experience issue

**Risk 6: Breaking Existing Functionality**
- **Mitigation:** Backward compatibility tests, feature flags
- **Impact:** High - must maintain existing features

---

## ✅ DELIVERABLES CHECKLIST

### Code Deliverables:
- [ ] `components/local_parser_scanner.py`
- [ ] `components/python_parser_analyzer.py`
- [ ] `components/python_to_lua_generator.py`
- [ ] `components/unified_lua_generator.py`
- [ ] Enhanced `orchestrator/core.py`
- [ ] Enhanced `main.py` (CLI)
- [ ] Enhanced `components/web_ui/routes.py` (GUI)
- [ ] Enhanced config.yaml.example
- [ ] 80+ new unit tests
- [ ] 10+ integration tests

### Documentation Deliverables:
- [ ] Updated README.md
- [ ] docs/USAGE_GUIDE.md (new)
- [ ] docs/development/PYTHON_PARSER_ARCHITECTURE.md (new)
- [ ] docs/development/ADDING_PARSER_TYPES.md (new)
- [ ] Updated docs/SETUP_GUIDE.md
- [ ] API documentation for new endpoints
- [ ] CLI usage examples
- [ ] GUI walkthrough

---

## 🎉 FINAL RECOMMENDATIONS

### Start Small, Scale Up

**Week 1: Proof of Concept**
1. Manually convert 3 Python parsers with Claude AI
2. Validate the approach works
3. Document learnings

**Week 2-3: Build Automation**
1. Implement LocalParserScanner
2. Implement Python analyzers/generators
3. Integrate with pipeline

**Week 4+: Production Deployment**
1. Convert all 36 Python OEM integrations
2. Test thoroughly
3. Deploy to production

---

## 📞 NEXT IMMEDIATE ACTIONS

**To Get Started Right Now:**

1. **Test Concept** (30 minutes):
   ```bash
   # Pick simple parser
   cd "Python OEM Integration Mapping/tenablevmsdlingest"

   # Ask me to convert it
   # I'll generate Lua from the Python mapping
   ```

2. **Prioritize Integrations** (15 minutes):
   - Which of the 36 integrations are most important?
   - Start with those for quick value

3. **Plan Development** (30 minutes):
   - Review this plan
   - Adjust timeline if needed
   - Assign resources

**Total Time to Production:** 3-4 weeks
**Immediate Value:** Can start converting manually TODAY

---

**Plan Status:** ✅ COMPLETE & READY FOR IMPLEMENTATION
**Next Action:** Approve plan and start Phase 1 or run proof of concept
**Questions?** Review and clarify any section

---

**END OF INTEGRATION PLAN**
