"""
Per-Parser Output Management
Handles structured output for each converted parser

DIRECTOR REQUIREMENT 3: Rebuild parsers into LUA and save as JSON
Creates per-parser directory structure with all required artifacts:
- analysis.json
- transform.lua
- pipeline.json
- validation_report.json

SECURITY FIX: Phase 1 - Path traversal protection implemented
All parser_id inputs are sanitized and validated to prevent arbitrary file writes
"""
import json
import logging
import re
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from components.manifest_schema import ParserManifest, validate_manifest

logger = logging.getLogger(__name__)


class ParserOutputManager:
    """
    Manages structured output for each parser conversion

    TRACEABILITY:
    - Requirement 3: Per-parser output structure
    - Creates output/<parser_id>/ with all artifacts
    - Maintains backward compatibility with aggregate files

    SECURITY:
    - Path traversal protection (Phase 1 Critical Fix)
    - Input sanitization for all parser_id values
    - Resolved path validation to ensure containment
    """

    def __init__(self, base_output_dir: str = "output"):
        """
        Initialize output manager

        Args:
            base_output_dir: Base directory for all outputs

        SECURITY: Base directory is resolved to absolute path for validation
        """
        self.base_output_dir = Path(base_output_dir).resolve()
        self.base_output_dir.mkdir(exist_ok=True)
        logger.info(f"Output manager initialized with base directory: {self.base_output_dir}")

    def create_parser_directory(self, parser_id: str) -> Path:
        """
        Create output directory for a parser with path traversal protection

        Args:
            parser_id: Unique parser identifier

        Returns:
            Path to parser output directory

        Raises:
            ValueError: If parser_id contains path traversal attempts or is invalid

        SECURITY: Phase 1 Critical Fix - Path Traversal Protection
        Implements multiple layers of protection:
        1. Input sanitization (remove ../, /, \\, dangerous chars)
        2. Character whitelist (alphanumeric, _, -)
        3. Path resolution validation (must be within base_output_dir)
        4. Prevents writing to base directory itself

        REQUIREMENT 3: Per-parser directory structure
        """
        # SECURITY: Sanitize input to prevent path traversal
        safe_id = self._sanitize_parser_id(parser_id)

        # Create path using sanitized ID
        parser_dir = self.base_output_dir / safe_id

        # SECURITY: Validate resolved path is within base directory
        try:
            resolved_parser_dir = parser_dir.resolve()
            resolved_base_dir = self.base_output_dir.resolve()

            # Check if resolved path starts with base path
            # Use as_posix() for consistent comparison across OS
            if not resolved_parser_dir.as_posix().startswith(resolved_base_dir.as_posix()):
                logger.error(
                    f"[LOCK] SECURITY: Path traversal attempt blocked!\n"
                    f"   Requested ID:    {parser_id}\n"
                    f"   Sanitized ID:    {safe_id}\n"
                    f"   Resolved path:   {resolved_parser_dir}\n"
                    f"   Base directory:  {resolved_base_dir}"
                )
                raise ValueError(
                    f"Path traversal blocked: parser_id '{parser_id}' resolves outside output directory"
                )

            # Additional check: ensure not the base directory itself
            if resolved_parser_dir == resolved_base_dir:
                logger.error(f"[LOCK] SECURITY: Attempt to use base directory as parser directory blocked")
                raise ValueError(
                    f"Invalid parser_id: '{parser_id}' resolves to base directory itself"
                )

        except ValueError:
            # Re-raise our validation errors
            raise
        except Exception as e:
            logger.error(f"Path validation failed for '{parser_id}': {e}")
            raise ValueError(f"Invalid parser_id: {parser_id}") from e

        # Path is safe, create directory
        parser_dir.mkdir(exist_ok=True, parents=True)
        logger.info(f"[OK] Created output directory: {parser_dir}")

        return parser_dir

    def _sanitize_parser_id(self, parser_id: str) -> str:
        """
        Sanitize parser_id to prevent path traversal attacks

        Args:
            parser_id: Raw parser identifier from untrusted source

        Returns:
            Sanitized parser identifier safe for filesystem use

        Raises:
            ValueError: If parser_id is empty

        SECURITY MEASURES:
        1. Replace path traversal sequences (../, .., /, \\)
        2. Remove all non-alphanumeric except _ and -
        3. Prevent hidden files (leading dots)
        4. Remove multiple consecutive underscores
        5. Limit length to prevent filesystem issues
        6. Ensure non-empty result with deterministic fallback

        Examples:
            "../../etc/passwd"        -> "etc_passwd"
            "../../../.ssh/keys"      -> "_ssh_keys"
            "valid-parser-123"        -> "valid-parser-123"
            "test/with/slashes"       -> "test_with_slashes"
            "test; rm -rf /"          -> "test_rm_rf"
        """
        if not parser_id:
            raise ValueError("parser_id cannot be empty")

        original_id = parser_id

        # Step 1: Replace path traversal sequences
        safe_id = parser_id.replace('..', '_')  # Remove parent directory references
        safe_id = safe_id.replace('/', '_')     # Remove forward slashes
        safe_id = safe_id.replace('\\', '_')    # Remove backslashes

        # Step 2: Remove dangerous characters - keep only alphanumeric, underscore, hyphen
        # This prevents:
        # - Null bytes (\x00)
        # - Shell metacharacters (;, |, &, $, `, etc.)
        # - Quote characters (', ")
        # - Control characters
        # - Unicode tricks
        safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', safe_id)

        # Step 3: Prevent hidden files (Unix/Linux dot files)
        while safe_id.startswith('.'):
            safe_id = '_' + safe_id[1:]

        # Step 4: Remove multiple consecutive underscores (aesthetics + security)
        safe_id = re.sub(r'_+', '_', safe_id)

        # Step 5: Trim underscores from start/end
        safe_id = safe_id.strip('_')

        # Step 6: Limit length (max 100 chars for filesystem compatibility)
        max_length = 100
        if len(safe_id) > max_length:
            # Hash the original to maintain uniqueness while truncating
            hash_suffix = hashlib.sha256(original_id.encode()).hexdigest()[:8]
            safe_id = safe_id[:max_length - 9] + '_' + hash_suffix

        # Step 7: Ensure non-empty (fallback to deterministic hash-based ID)
        if not safe_id:
            # Generate deterministic ID from hash of original
            hash_value = hashlib.sha256(original_id.encode()).hexdigest()[:12]
            safe_id = f"parser_{hash_value}"
            logger.warning(f"Parser ID was empty after sanitization, using hash-based ID: {safe_id}")

        # Log sanitization if significant changes were made
        if safe_id != original_id:
            logger.warning(
                f"[LOCK] Parser ID sanitized for security:\n"
                f"   Original:  '{original_id}'\n"
                f"   Sanitized: '{safe_id}'"
            )

        return safe_id

    def save_analysis(self, parser_id: str, analysis_data: Dict[str, Any]) -> Path:
        """
        Save analysis.json

        Args:
            parser_id: Parser identifier
            analysis_data: Analysis results from Claude

        Returns:
            Path to saved file

        REQUIREMENT 3: analysis.json artifact
        Contains Claude's analysis of the SentinelOne parser
        """
        parser_dir = self.create_parser_directory(parser_id)
        analysis_file = parser_dir / "analysis.json"

        # Add metadata
        analysis_with_metadata = {
            "parser_id": parser_id,
            "analyzed_at": datetime.now().isoformat(),
            "analyzer": "claude-3-5-sonnet",
            "analysis": analysis_data
        }

        with open(analysis_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_with_metadata, f, indent=2)

        logger.info(f"Saved analysis: {analysis_file}")
        return analysis_file

    def save_lua_transform(self, parser_id: str, lua_code: str, metadata: Optional[Dict] = None) -> Path:
        """
        Save transform.lua

        Args:
            parser_id: Parser identifier
            lua_code: Generated LUA transformation code
            metadata: Optional metadata about generation

        Returns:
            Path to saved file

        REQUIREMENT 3: transform.lua artifact
        Contains the generated LUA transformation function
        """
        parser_dir = self.create_parser_directory(parser_id)
        lua_file = parser_dir / "transform.lua"

        # Add header comment with metadata
        header = f"""--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: {parser_id}
  Generated: {datetime.now().isoformat()}
  Generator: Purple Pipeline Parser Eater v10.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

"""
        full_content = header + lua_code

        with open(lua_file, 'w', encoding='utf-8') as f:
            f.write(full_content)

        logger.info(f"Saved LUA transform: {lua_file}")
        return lua_file

    def save_pipeline_json(self, parser_id: str, pipeline_data: Dict[str, Any]) -> Path:
        """
        Save pipeline.json (complete Observo payload)

        Args:
            parser_id: Parser identifier
            pipeline_data: Full Observo pipeline definition

        Returns:
            Path to saved file

        REQUIREMENT 3: pipeline.json artifact
        Complete Observo pipeline payload ready for API upload
        Includes metadata, source, transforms, and destination
        """
        parser_dir = self.create_parser_directory(parser_id)
        pipeline_file = parser_dir / "pipeline.json"

        # Ensure required structure
        complete_pipeline = {
            "parser_id": parser_id,
            "created_at": datetime.now().isoformat(),
            "pipeline": pipeline_data
        }

        with open(pipeline_file, 'w', encoding='utf-8') as f:
            json.dump(complete_pipeline, f, indent=2)

        logger.info(f"Saved pipeline JSON: {pipeline_file}")
        return pipeline_file

    def save_validation_report(self, parser_id: str, validation_results: Dict[str, Any]) -> Path:
        """
        Save validation_report.json

        Args:
            parser_id: Parser identifier
            validation_results: Validation test results

        Returns:
            Path to saved file

        REQUIREMENT 4: validation_report.json artifact
        Contains results of all validation checks:
        - Schema validation
        - Syntax validation
        - Field extraction verification
        - Sample event tests
        """
        parser_dir = self.create_parser_directory(parser_id)
        validation_file = parser_dir / "validation_report.json"

        # Add metadata
        complete_report = {
            "parser_id": parser_id,
            "validated_at": datetime.now().isoformat(),
            "validation_version": "1.0.0",
            "results": validation_results
        }

        with open(validation_file, 'w', encoding='utf-8') as f:
            json.dump(complete_report, f, indent=2)

        logger.info(f"Saved validation report: {validation_file}")
        return validation_file

    def save_manifest(self, parser_id: str, manifest_data: Dict[str, Any], mode: str = "stable") -> Path:
        """Save manifest metadata for the parser (stable/canary)."""
        parser_dir = self.create_parser_directory(parser_id)
        filename = "manifest.json" if mode == "stable" else f"manifest-{mode}.json"
        manifest_file = parser_dir / filename

        manifest = {
            "manifest_version": manifest_data.get("manifest_version", "1.0"),
            "parser_id": parser_id,
            "generated_at": datetime.now().isoformat(),
            **manifest_data,
        }
        manifest.setdefault("deployment", {})
        manifest["deployment"]["mode"] = mode

        validated = validate_manifest(manifest)
        with open(manifest_file, "w", encoding="utf-8") as handle:
            json.dump(validated.dict(), handle, indent=2, default=str)
        logger.info(f"Saved manifest: {manifest_file}")

        if mode == "stable" and manifest_file.name != "manifest.json":
            default_file = parser_dir / "manifest.json"
            with open(default_file, "w", encoding="utf-8") as handle:
                json.dump(validated.dict(), handle, indent=2, default=str)

        return manifest_file

    def save_all_artifacts(
        self,
        parser_id: str,
        analysis_data: Dict[str, Any],
        lua_code: str,
        pipeline_data: Dict[str, Any],
        validation_results: Dict[str, Any],
        manifest_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Path]:
        """
        Save all per-parser artifacts in one call

        Args:
            parser_id: Parser identifier
            analysis_data: Analysis results
            lua_code: Generated LUA code
            pipeline_data: Pipeline definition
            validation_results: Validation results

        Returns:
            Dictionary of artifact type -> file path

        REQUIREMENT 3: Complete per-parser output
        One-shot creation of all required files
        """
        logger.info(f"Saving all artifacts for parser: {parser_id}")

        artifacts = {
            "analysis": self.save_analysis(parser_id, analysis_data),
            "lua": self.save_lua_transform(parser_id, lua_code),
            "pipeline": self.save_pipeline_json(parser_id, pipeline_data),
            "validation": self.save_validation_report(parser_id, validation_results)
        }
        if manifest_data:
            artifacts["manifest"] = self.save_manifest(parser_id, manifest_data, mode="stable")

        logger.info(f"[OK] All artifacts saved for {parser_id}")
        return artifacts

    def get_parser_output_dir(self, parser_id: str) -> Path:
        """Get the output directory for a parser"""
        return self.base_output_dir / parser_id

    def parser_exists(self, parser_id: str) -> bool:
        """Check if parser output directory exists"""
        return self.get_parser_output_dir(parser_id).exists()

    def load_artifact(self, parser_id: str, artifact_type: str) -> Optional[Dict]:
        """
        Load a specific artifact for a parser

        Args:
            parser_id: Parser identifier
            artifact_type: Type of artifact (analysis, pipeline, validation)

        Returns:
            Loaded artifact data or None if not found
        """
        parser_dir = self.get_parser_output_dir(parser_id)

        artifact_files = {
            "analysis": "analysis.json",
            "pipeline": "pipeline.json",
            "validation": "validation_report.json"
        }

        if artifact_type not in artifact_files:
            return None

        artifact_file = parser_dir / artifact_files[artifact_type]

        if not artifact_file.exists():
            return None

        try:
            with open(artifact_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load {artifact_type} for {parser_id}: {e}")
            return None

    def load_lua_transform(self, parser_id: str) -> Optional[str]:
        """Load the LUA transform code for a parser"""
        parser_dir = self.get_parser_output_dir(parser_id)
        lua_file = parser_dir / "transform.lua"

        if not lua_file.exists():
            return None

        try:
            with open(lua_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load LUA for {parser_id}: {e}")
            return None

    def list_converted_parsers(self) -> List[str]:
        """
        List all parsers that have been converted

        Returns:
            List of parser IDs with output directories
        """
        if not self.base_output_dir.exists():
            return []

        return [
            d.name for d in self.base_output_dir.iterdir()
            if d.is_dir() and (d / "pipeline.json").exists()
        ]

    def get_conversion_summary(self) -> Dict[str, Any]:
        """
        Get summary of all conversions

        Returns:
            Summary statistics about converted parsers
        """
        converted = self.list_converted_parsers()

        summary = {
            "total_conversions": len(converted),
            "parsers": []
        }

        for parser_id in converted:
            parser_info = {
                "parser_id": parser_id,
                "has_analysis": (self.get_parser_output_dir(parser_id) / "analysis.json").exists(),
                "has_lua": (self.get_parser_output_dir(parser_id) / "transform.lua").exists(),
                "has_pipeline": (self.get_parser_output_dir(parser_id) / "pipeline.json").exists(),
                "has_validation": (self.get_parser_output_dir(parser_id) / "validation_report.json").exists()
            }

            # Load validation status if available
            validation = self.load_artifact(parser_id, "validation")
            if validation:
                parser_info["validation_passed"] = validation.get("results", {}).get("overall_status") == "passed"

            summary["parsers"].append(parser_info)

        return summary
