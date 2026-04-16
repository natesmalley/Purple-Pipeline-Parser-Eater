"""
User Feedback Collection and Learning System
Collects feedback to continuously improve the conversion system.

Write path persists every record to a JSONL file on disk (atomic
O_APPEND, following the same pattern as ``feedback_channel.py``).
The optional RAG knowledge base is a best-effort secondary sink.
"""

import logging
import asyncio
import json
import os
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from difflib import unified_diff

try:
    from utils.error_handler import handle_api_errors
except ImportError:
    from ..utils.error_handler import handle_api_errors


logger = logging.getLogger(__name__)

# POSIX PIPE_BUF — records whose JSON-encoded form fits within this
# limit are appended atomically via a single os.write on O_APPEND fds.
_PIPE_BUF = 4096

_DEFAULT_CORRECTIONS_PATH = os.path.join("data", "feedback", "corrections.jsonl")


# ---------------------------------------------------------------------------
# Module-level helper: format corrections for LLM prompts
# ---------------------------------------------------------------------------

def read_corrections_for_prompt(
    parser_name: str,
    ocsf_class_uid: Optional[int] = None,
    vendor: Optional[str] = None,
    feedback_system: Optional["FeedbackSystem"] = None,
    limit: int = 2,
) -> List[str]:
    """Return formatted correction strings ready to inject into an LLM prompt.

    Queries ``feedback_system.read_corrections_for_parser`` (if available)
    and returns compact before/after/reason strings bounded by
    ``WORKBENCH_MAX_SAMPLE_CHARS``.  Never raises; backend errors return
    ``[]``.

    This is the shared extraction point used by both ``LuaGenerator`` and
    ``AgenticLuaGenerator``.
    """
    if feedback_system is None:
        # Try to build a stateless reader (JSONL-only, no KB)
        feedback_system = FeedbackSystem(config={}, knowledge_base=None)

    try:
        records = feedback_system.read_corrections_for_parser(
            parser_name=parser_name,
            ocsf_class_uid=ocsf_class_uid,
            vendor=vendor,
            limit=limit,
        )
        return [_format_correction_for_prompt(r) for r in records]
    except Exception as exc:  # noqa: BLE001
        logger.warning("read_corrections_for_prompt failed (non-fatal): %s", exc)
        return []


def _format_correction_for_prompt(record: Dict) -> str:
    """Compact correction string bounded by WORKBENCH_MAX_SAMPLE_CHARS."""
    try:
        max_chars = int(
            os.environ.get("WORKBENCH_MAX_SAMPLE_CHARS", "150000")
        )
    except ValueError:
        max_chars = 150000
    before = str(record.get("before", ""))[: max(1, max_chars // 4)]
    after = str(record.get("after", ""))[: max(1, max_chars // 4)]
    reason = str(record.get("reason", ""))[: max(1, max_chars // 8)]
    return (
        "Prior correction:\n"
        "  Before: %s\n"
        "  After: %s\n"
        "  Why: %s" % (before, after, reason)
    )


class FeedbackSystem:
    """
    Collects user feedback and system performance data for machine learning

    Feedback Types:
    1. User corrections to generated LUA
    2. Deployment success/failure
    3. Runtime performance metrics
    4. User ratings and comments
    5. Error reports and resolutions
    """

    def __init__(self, config: Dict, knowledge_base):
        self.config = config
        self.knowledge_base = knowledge_base
        self._jsonl_lock = threading.Lock()

        corrections_env = os.environ.get(
            "FEEDBACK_CORRECTIONS_PATH", ""
        ).strip()
        self._corrections_path = Path(
            corrections_env if corrections_env else _DEFAULT_CORRECTIONS_PATH
        )

        self.statistics = {
            'corrections_recorded': 0,
            'deployments_tracked': 0,
            'performance_metrics': 0,
            'errors_recorded': 0,
            'total_feedback_items': 0
        }

    # -----------------------------------------------------------------
    # Shared persistence helper (JSONL + optional RAG KB)
    # -----------------------------------------------------------------

    def _persist_record(
        self,
        doc_type: str,
        content: str,
        metadata: Dict,
    ) -> str:
        """Persist a feedback record to the JSONL file on disk.

        Small records (JSON <= 4096 bytes) are appended atomically via
        ``O_APPEND``.  Large records are written to a sibling file and a
        compact pointer is appended to the JSONL index instead.

        If ``self.knowledge_base`` exposes a callable ``add_document``,
        that is also invoked as a best-effort secondary sink.

        Returns the ``correction_id`` assigned to the record.
        """
        correction_id = uuid.uuid4().hex[:12]
        now_iso = datetime.now(timezone.utc).isoformat()

        record = {
            "correction_id": correction_id,
            "doc_type": doc_type,
            "content": content,
            **metadata,
            "recorded_at": now_iso,
        }

        encoded = json.dumps(record, sort_keys=True, default=str)
        encoded_bytes = (encoded + "\n").encode("utf-8")

        self._corrections_path.parent.mkdir(parents=True, exist_ok=True)

        if len(encoded_bytes) <= _PIPE_BUF:
            self._append_bytes(encoded_bytes)
        else:
            # Write full record to a sibling file, append a pointer
            sibling_name = "corrections-%s.json" % correction_id
            sibling_path = self._corrections_path.parent / sibling_name
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=str(self._corrections_path.parent),
                suffix=".tmp",
            )
            try:
                os.write(tmp_fd, encoded.encode("utf-8"))
                os.fsync(tmp_fd)
            finally:
                os.close(tmp_fd)
            os.replace(tmp_path, str(sibling_path))

            pointer = {
                "correction_id": correction_id,
                "doc_type": doc_type,
                "parser_name": metadata.get("parser_name"),
                "recorded_at": now_iso,
                "_ref": sibling_name,
            }
            ptr_bytes = (
                json.dumps(pointer, sort_keys=True, default=str) + "\n"
            ).encode("utf-8")
            self._append_bytes(ptr_bytes)

        # Best-effort secondary: RAG knowledge base
        add_doc = getattr(self.knowledge_base, "add_document", None)
        if callable(add_doc):
            try:
                import asyncio as _aio
                result = add_doc(content=content, metadata=metadata)
                # Handle both sync and async callables
                if _aio.iscoroutine(result):
                    try:
                        loop = _aio.get_running_loop()
                    except RuntimeError:
                        loop = None
                    if loop and loop.is_running():
                        _aio.ensure_future(result)
                    else:
                        _aio.run(result)
            except Exception as exc:
                logger.warning(
                    "knowledge_base.add_document failed (non-fatal): %s",
                    exc,
                )

        return correction_id

    def _append_bytes(self, data: bytes) -> None:
        """Atomically append *data* to the corrections JSONL file."""
        with self._jsonl_lock:
            fd = os.open(
                str(self._corrections_path),
                os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                0o644,
            )
            try:
                os.write(fd, data)
                try:
                    os.fsync(fd)
                except OSError:
                    logger.debug(
                        "fsync failed for %s", self._corrections_path
                    )
            finally:
                os.close(fd)

    async def record_lua_correction(
        self,
        parser_name: str,
        original_lua: str,
        corrected_lua: str,
        correction_reason: str,
        user_id: Optional[str] = None
    ):
        """
        Record when user corrects generated LUA code

        This is CRITICAL for learning - these corrections show us
        where our generation is wrong and how to improve it

        Args:
            parser_name: Name of the parser
            original_lua: The LUA code we generated
            corrected_lua: The LUA code after user corrections
            correction_reason: Why the user made the correction
            user_id: Optional identifier for the user
        """
        logger.info(f"Recording user correction for parser: {parser_name}")

        try:
            # Calculate detailed diff
            diff = self._compute_detailed_diff(original_lua, corrected_lua)

            # Classify the type of correction
            correction_type = self._classify_correction(diff, correction_reason)

            # Extract lessons learned
            lessons = self._extract_lessons(diff, correction_reason, correction_type)

            # Build comprehensive feedback document
            document_content = f"""
USER CORRECTION - {parser_name}

Correction Type: {correction_type}
Timestamp: {datetime.now().isoformat()}
User: {user_id or 'Anonymous'}

REASON FOR CORRECTION:
{correction_reason}

ORIGINAL LUA (GENERATED BY SYSTEM):
{original_lua}

CORRECTED LUA (USER MODIFIED):
{corrected_lua}

DETAILED DIFF:
{diff}

LESSONS LEARNED:
{chr(10).join(f'  - {lesson}' for lesson in lessons)}

PATTERN TO AVOID IN FUTURE:
{self._extract_antipattern(original_lua, diff)}

PATTERN TO USE IN FUTURE:
{self._extract_good_pattern(corrected_lua, diff)}

IMPACT:
This correction helps the system learn:
1. What NOT to generate (antipattern)
2. What TO generate instead (correct pattern)
3. Context where this applies ({correction_type})
"""

            # Persist to JSONL (primary) + optional RAG KB (secondary)
            doc_id = self._persist_record(
                doc_type="correction_example",
                content=document_content,
                metadata={
                    "title": "User Correction: %s" % parser_name,
                    "source": "user_feedback",
                    "parser_name": parser_name,
                    "correction_type": correction_type,
                    "user_id": user_id or "anonymous",
                    "severity": self._assess_correction_severity(diff),
                },
            )

            self.statistics['corrections_recorded'] += 1
            self.statistics['total_feedback_items'] += 1

            logger.info(
                "[OK] Recorded correction for %s (ID: %s)",
                parser_name, doc_id,
            )

            return doc_id

        except Exception as e:
            logger.error(f"Failed to record correction: {e}")
            raise

    def _compute_detailed_diff(self, original: str, corrected: str) -> str:
        """Compute detailed line-by-line diff"""
        original_lines = original.splitlines(keepends=True)
        corrected_lines = corrected.splitlines(keepends=True)

        diff = unified_diff(
            original_lines,
            corrected_lines,
            fromfile='generated.lua',
            tofile='corrected.lua',
            lineterm=''
        )

        return '\n'.join(diff)

    def _classify_correction(self, diff: str, reason: str) -> str:
        """Classify the type of correction made"""

        reason_lower = reason.lower()

        # Classification based on reason and diff content
        if 'field' in reason_lower or 'mapping' in reason_lower:
            return 'field_mapping_error'
        elif 'performance' in reason_lower or 'optimization' in reason_lower:
            return 'performance_improvement'
        elif 'error' in reason_lower or 'crash' in reason_lower or 'fail' in reason_lower:
            return 'error_handling'
        elif 'security' in reason_lower or 'validation' in reason_lower:
            return 'security_issue'
        elif 'logic' in reason_lower or 'incorrect' in reason_lower:
            return 'logic_error'
        elif 'syntax' in reason_lower:
            return 'syntax_error'
        elif 'type' in reason_lower or 'conversion' in reason_lower:
            return 'type_conversion_error'
        else:
            return 'other_improvement'

    def _extract_lessons(
        self,
        diff: str,
        reason: str,
        correction_type: str
    ) -> List[str]:
        """Extract specific lessons from the correction"""
        lessons = []

        # Lesson based on correction type
        type_lessons = {
            'field_mapping_error': [
                'Double-check OCSF field names for accuracy',
                'Verify source field exists before mapping',
                'Ensure field types match OCSF schema'
            ],
            'performance_improvement': [
                'Consider optimization opportunities in generated code',
                'Look for redundant operations that can be eliminated',
                'Use more efficient LUA constructs'
            ],
            'error_handling': [
                'Add nil checks before field access',
                'Implement pcall() for risky operations',
                'Provide fallback values for missing data'
            ],
            'security_issue': [
                'Validate and sanitize all input data',
                'Avoid code injection vulnerabilities',
                'Implement proper access controls'
            ],
            'logic_error': [
                'Review business logic more carefully',
                'Test edge cases and boundary conditions',
                'Verify conditional logic is correct'
            ]
        }

        lessons.extend(type_lessons.get(correction_type, ['Review similar cases for patterns']))

        # Add reason-specific lesson
        lessons.append(f"User feedback: {reason}")

        return lessons

    def _extract_antipattern(self, original: str, diff: str) -> str:
        """Extract the antipattern (what not to do)"""
        # Look for removed lines in diff (lines starting with -)
        removed_lines = [
            line[1:].strip() for line in diff.split('\n')
            if line.startswith('-') and not line.startswith('---')
        ]

        if removed_lines:
            return '\n'.join(f'  AVOID: {line}' for line in removed_lines[:5])
        else:
            return '  (No specific antipattern identified)'

    def _extract_good_pattern(self, corrected: str, diff: str) -> str:
        """Extract the good pattern (what to do instead)"""
        # Look for added lines in diff (lines starting with +)
        added_lines = [
            line[1:].strip() for line in diff.split('\n')
            if line.startswith('+') and not line.startswith('+++')
        ]

        if added_lines:
            return '\n'.join(f'  USE: {line}' for line in added_lines[:5])
        else:
            return '  (No specific pattern identified)'

    def _assess_correction_severity(self, diff: str) -> str:
        """Assess how severe/important the correction is"""
        lines_changed = len([
            line for line in diff.split('\n')
            if line.startswith(('+', '-'))
        ])

        if lines_changed <= 2:
            return 'minor'
        elif lines_changed <= 10:
            return 'moderate'
        else:
            return 'major'

    async def record_deployment_result(
        self,
        parser_name: str,
        lua_code: str,
        success: bool,
        error_message: Optional[str] = None,
        deployment_time_sec: Optional[float] = None
    ):
        """
        Record deployment success or failure

        Args:
            parser_name: Name of the parser
            lua_code: The LUA code that was deployed
            success: Whether deployment succeeded
            error_message: Error message if failed
            deployment_time_sec: Time taken to deploy
        """
        logger.info(f"Recording deployment result for {parser_name}: {'SUCCESS' if success else 'FAILURE'}")

        try:
            document_content = f"""
DEPLOYMENT RESULT - {parser_name}

Status: {'[OK] SUCCESS' if success else '[ERROR] FAILURE'}
Timestamp: {datetime.now().isoformat()}
Deployment Time: {deployment_time_sec or 'N/A'} seconds

DEPLOYED LUA CODE:
{lua_code}

{'ERROR DETAILS:' + chr(10) + error_message if error_message else 'Deployment completed successfully'}

LEARNING VALUE:
{'This is a proven working example - use similar patterns' if success else 'Avoid this pattern - it failed deployment'}
"""

            doc_id = self._persist_record(
                doc_type="deployment_result",
                content=document_content,
                metadata={
                    "title": "Deployment: %s" % parser_name,
                    "source": "deployment_tracking",
                    "parser_name": parser_name,
                    "success": success,
                    "deployment_time": deployment_time_sec,
                },
            )

            self.statistics['deployments_tracked'] += 1
            self.statistics['total_feedback_items'] += 1

            return doc_id

        except Exception as e:
            logger.error("Failed to record deployment result: %s", e)
            raise

    async def record_performance_metrics(
        self,
        parser_name: str,
        metrics: Dict
    ):
        """
        Record runtime performance metrics

        Args:
            parser_name: Name of the parser
            metrics: Dictionary of performance metrics
                     Expected keys: events_per_second, avg_latency_ms,
                                   memory_mb, cpu_percent, error_rate
        """
        logger.info(f"Recording performance metrics for {parser_name}")

        try:
            document_content = f"""
PERFORMANCE METRICS - {parser_name}

Timestamp: {datetime.now().isoformat()}

THROUGHPUT:
  - Events/second: {metrics.get('events_per_second', 'N/A')}
  - Average latency: {metrics.get('avg_latency_ms', 'N/A')}ms
  - Peak events/sec: {metrics.get('peak_events_per_second', 'N/A')}

RESOURCE USAGE:
  - Memory: {metrics.get('memory_mb', 'N/A')}MB
  - CPU: {metrics.get('cpu_percent', 'N/A')}%
  - Disk I/O: {metrics.get('disk_io_mb', 'N/A')}MB

RELIABILITY:
  - Error rate: {metrics.get('error_rate', 'N/A')}%
  - Success rate: {metrics.get('success_rate', 'N/A')}%
  - Total events processed: {metrics.get('total_events', 'N/A')}

OPTIMIZATION LEVEL:
  - {self._assess_performance(metrics)}
"""

            doc_id = self._persist_record(
                doc_type="performance_metrics",
                content=document_content,
                metadata={
                    "title": "Performance: %s" % parser_name,
                    "source": "performance_monitoring",
                    "parser_name": parser_name,
                    "events_per_second": metrics.get('events_per_second'),
                    "memory_mb": metrics.get('memory_mb'),
                    "error_rate": metrics.get('error_rate'),
                },
            )

            self.statistics['performance_metrics'] += 1
            self.statistics['total_feedback_items'] += 1

            return doc_id

        except Exception as e:
            logger.error("Failed to record performance metrics: %s", e)
            raise

    def _assess_performance(self, metrics: Dict) -> str:
        """Assess overall performance quality"""
        eps = metrics.get('events_per_second', 0)
        error_rate = metrics.get('error_rate', 100)

        if eps >= 10000 and error_rate < 1:
            return 'EXCELLENT - High throughput, low errors'
        elif eps >= 5000 and error_rate < 5:
            return 'GOOD - Acceptable throughput and error rate'
        elif eps >= 1000 and error_rate < 10:
            return 'FAIR - Moderate performance, room for improvement'
        else:
            return 'POOR - Performance optimization needed'

    async def record_conversion_error(
        self,
        parser_name: str,
        stage: str,
        error: Exception,
        parser_content: str,
        attempted_fixes: Optional[List[str]] = None
    ):
        """
        Record conversion errors and failures

        Args:
            parser_name: Name of the parser
            stage: Stage where error occurred (analysis/generation/deployment)
            error: The exception that occurred
            parser_content: The parser content that failed
            attempted_fixes: List of fixes that were attempted
        """
        logger.info(f"Recording conversion error for {parser_name} at stage: {stage}")

        try:
            document_content = f"""
CONVERSION ERROR - {parser_name}

Failed at Stage: {stage}
Timestamp: {datetime.now().isoformat()}

ERROR DETAILS:
  Type: {type(error).__name__}
  Message: {str(error)}

PARSER CONTENT:
{parser_content[:1000]}...  # Truncate for readability

ATTEMPTED FIXES:
{chr(10).join(f'  {i+1}. {fix}' for i, fix in enumerate(attempted_fixes or ['None'])) }

ROOT CAUSE ANALYSIS:
{self._analyze_error_root_cause(error, parser_content)}

LESSONS FOR FUTURE:
{self._extract_error_lessons(error, stage)}
"""

            doc_id = self._persist_record(
                doc_type="conversion_error",
                content=document_content,
                metadata={
                    "title": "Error: %s" % parser_name,
                    "source": "error_tracking",
                    "parser_name": parser_name,
                    "error_type": type(error).__name__,
                    "stage": stage,
                },
            )

            self.statistics['errors_recorded'] += 1
            self.statistics['total_feedback_items'] += 1

            return doc_id

        except Exception as e:
            logger.error("Failed to record conversion error: %s", e)
            # Don't raise - error recording shouldn't break the system

    def _analyze_error_root_cause(self, error: Exception, parser_content: str) -> str:
        """Analyze the root cause of an error"""
        error_type = type(error).__name__

        causes = {
            'JSONDecodeError': 'Parser content is not valid JSON',
            'KeyError': 'Required field missing in parser definition',
            'TypeError': 'Data type mismatch in processing',
            'ValueError': 'Invalid value encountered during conversion',
            'AttributeError': 'Attempting to access non-existent attribute',
            'TimeoutError': 'Operation took too long to complete',
            'ClaudeAPIError': 'Claude AI API request failed'
        }

        return causes.get(error_type, f'Unknown error type: {error_type}')

    def _extract_error_lessons(self, error: Exception, stage: str) -> str:
        """Extract lessons from error"""
        lessons = [
            f'Add better error handling for {type(error).__name__} in {stage} stage',
            'Validate input data before processing',
            'Implement retry logic for transient failures'
        ]

        return '\n'.join(f'  - {lesson}' for lesson in lessons)

    async def record_lua_generation_success(
        self,
        parser_name: str,
        lua_code: str,
        generation_time_sec: float,
        confidence_score: Optional[float] = None,
        strategy: Optional[str] = None
    ):
        """
        Record successful LUA code generation for learning and metrics.

        This method tracks successful conversions to identify patterns that work well
        and to build a library of known-good transformations.

        Args:
            parser_name: Name of the parser
            lua_code: The successfully generated LUA code
            generation_time_sec: Time taken to generate (seconds)
            confidence_score: Optional confidence score (0.0-1.0)
            strategy: Optional generation strategy used
        """
        logger.info(f"Recording successful LUA generation for parser: {parser_name}")

        try:
            document_content = f"""
LUA GENERATION SUCCESS - {parser_name}

Timestamp: {datetime.now().isoformat()}
Generation Time: {generation_time_sec:.2f} seconds
Confidence Score: {confidence_score if confidence_score else 'N/A'}
Strategy Used: {strategy if strategy else 'default'}

GENERATED LUA CODE:
{lua_code}

SUCCESS METRICS:
  - Parser converted successfully
  - Code passed validation
  - Ready for deployment

LESSONS LEARNED:
  - This parser pattern works well with {strategy if strategy else 'default'} strategy
  - Generation time: {self._categorize_generation_time(generation_time_sec)}
  - Add to successful patterns library
"""

            self._persist_record(
                doc_type="lua_generation_success",
                content=document_content,
                metadata={
                    'parser_name': parser_name,
                    'generation_time': generation_time_sec,
                    'confidence_score': confidence_score,
                    'strategy': strategy,
                },
            )

            self.statistics['total_feedback_items'] += 1
            logger.info("Success recorded for %s", parser_name)

        except Exception as e:
            logger.error("Failed to record LUA generation success: %s", e)

    async def record_lua_generation_failure(
        self,
        parser_name: str,
        error_message: str,
        attempted_strategy: Optional[str] = None,
        parser_content: Optional[str] = None,
        error_type: Optional[str] = None
    ):
        """
        Record LUA generation failure for learning and improvement.

        This method tracks failed conversions to identify problematic patterns
        and improve the generation logic.

        Args:
            parser_name: Name of the parser that failed
            error_message: Error message or failure reason
            attempted_strategy: Strategy that was attempted
            parser_content: Optional parser content for analysis
            error_type: Optional classification of error
        """
        logger.info(f"Recording LUA generation failure for parser: {parser_name}")

        try:
            document_content = f"""
LUA GENERATION FAILURE - {parser_name}

Timestamp: {datetime.now().isoformat()}
Strategy Attempted: {attempted_strategy if attempted_strategy else 'unknown'}
Error Type: {error_type if error_type else 'unclassified'}

ERROR DETAILS:
{error_message}

PARSER CONTENT (truncated):
{parser_content[:500] if parser_content else 'Not available'}...

FAILURE ANALYSIS:
  - Pattern failed with {attempted_strategy if attempted_strategy else 'default'} strategy
  - May need alternative approach
  - Add to problematic patterns database

RECOMMENDATIONS:
  - Try alternative generation strategy
  - Review similar successful conversions
  - Consider manual intervention
  - Update generation rules to handle this pattern
"""

            self._persist_record(
                doc_type="lua_generation_failure",
                content=document_content,
                metadata={
                    'parser_name': parser_name,
                    'attempted_strategy': attempted_strategy,
                    'error_type': error_type,
                },
            )

            self.statistics['errors_recorded'] += 1
            self.statistics['total_feedback_items'] += 1
            logger.info("Failure recorded for %s", parser_name)

        except Exception as e:
            logger.error("Failed to record LUA generation failure: %s", e)

    def _categorize_generation_time(self, time_sec: float) -> str:
        """Categorize generation time as fast/normal/slow"""
        if time_sec < 5:
            return "FAST (< 5s)"
        elif time_sec < 15:
            return "NORMAL (5-15s)"
        else:
            return f"SLOW ({time_sec:.1f}s - may need optimization)"

    def read_corrections_for_parser(
        self,
        parser_name: str,
        ocsf_class_uid: Optional[int] = None,
        vendor: Optional[str] = None,
        limit: int = 2,
    ) -> List[Dict[str, Any]]:
        """Return the top-N corrections matching the filter, most recent first.

        Phase 3.I (plan Stream C). Synchronous, side-effect free reader used
        by ``LuaGenerator._read_feedback_corrections`` to inject prior
        user corrections as few-shot hints.

        Data sources (checked in order, deduplicated by correction_id):
        1. JSONL file on disk (``_corrections_path``), resolving any
           ``_ref`` pointers to sibling JSON files.
        2. Knowledge base (optional RAG dependency) via the existing
           search / list_documents / all_documents probing chain.

        Returns a list of dicts with ``{before, after, reason, recorded_at,
        correction_id}``. Records stored in the legacy diff shape
        (``original_lua`` / ``corrected_lua`` / ``diff``) are mapped to
        the same shape.

        Returns ``[]`` when no records match or on error (logged WARNING).
        """
        try:
            seen_ids: set = set()
            matches: List[Dict[str, Any]] = []

            # --- Source 1: JSONL on disk ---
            self._read_jsonl_corrections(
                parser_name, ocsf_class_uid, vendor,
                matches, seen_ids,
            )

            # --- Source 2: knowledge base ---
            if self.knowledge_base is not None:
                self._read_kb_corrections(
                    parser_name, ocsf_class_uid, vendor,
                    matches, seen_ids,
                )

            matches.sort(
                key=lambda r: r.get("recorded_at") or "",
                reverse=True,
            )
            return matches[: max(0, int(limit))]

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "read_corrections_for_parser failed (non-fatal): %s", exc
            )
            return []

    # -- JSONL reader helper --

    def _read_jsonl_corrections(
        self,
        parser_name: str,
        ocsf_class_uid: Optional[int],
        vendor: Optional[str],
        out: List[Dict[str, Any]],
        seen_ids: set,
    ) -> None:
        """Read correction records from the JSONL file on disk."""
        try:
            if not self._corrections_path.exists():
                return
            with open(self._corrections_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    if not isinstance(rec, dict):
                        continue

                    # Resolve _ref pointers to sibling files
                    ref = rec.get("_ref")
                    if ref:
                        sibling = self._corrections_path.parent / ref
                        try:
                            full_rec = json.loads(
                                sibling.read_text(encoding="utf-8")
                            )
                            if isinstance(full_rec, dict):
                                rec = full_rec
                        except Exception:
                            continue

                    if rec.get("doc_type") != "correction_example":
                        continue
                    if rec.get("parser_name") != parser_name:
                        continue
                    if (
                        ocsf_class_uid is not None
                        and rec.get("ocsf_class_uid") != ocsf_class_uid
                    ):
                        continue
                    if vendor is not None and rec.get("vendor") != vendor:
                        continue

                    cid = rec.get("correction_id", "")
                    if cid and cid in seen_ids:
                        continue
                    if cid:
                        seen_ids.add(cid)

                    out.append(self._normalize_correction_record(rec))
        except Exception as exc:
            logger.warning(
                "JSONL corrections read failed (non-fatal): %s", exc
            )

    # -- KB reader helper (original probe chain) --

    def _read_kb_corrections(
        self,
        parser_name: str,
        ocsf_class_uid: Optional[int],
        vendor: Optional[str],
        out: List[Dict[str, Any]],
        seen_ids: set,
    ) -> None:
        """Read correction records from the knowledge base."""
        try:
            raw_records: List[Any] = []
            search = getattr(self.knowledge_base, "search", None)
            if callable(search):
                try:
                    raw_records = list(search(
                        doc_type="correction_example",
                        parser_name=parser_name,
                    )) or []
                except TypeError:
                    raw_records = list(search()) or []
            else:
                fallback_attrs = (
                    "search_knowledge",
                    "list_documents",
                    "all_documents",
                )
                for attr in fallback_attrs:
                    candidate = getattr(
                        self.knowledge_base, attr, None
                    )
                    if callable(candidate):
                        try:
                            raw_records = list(candidate(
                                doc_type_filter="correction_example",
                            )) or []
                        except TypeError:
                            raw_records = list(candidate()) or []
                        break

            for rec in raw_records:
                if not isinstance(rec, dict):
                    continue
                meta_val = rec.get("metadata")
                meta = (
                    meta_val if isinstance(meta_val, dict) else rec
                )
                if meta.get("doc_type") != "correction_example":
                    continue
                if meta.get("parser_name") != parser_name:
                    continue
                if (
                    ocsf_class_uid is not None
                    and meta.get("ocsf_class_uid") != ocsf_class_uid
                ):
                    continue
                if vendor is not None and meta.get("vendor") != vendor:
                    continue

                cid = (
                    rec.get("correction_id")
                    or meta.get("correction_id")
                    or ""
                )
                if cid and cid in seen_ids:
                    continue
                if cid:
                    seen_ids.add(cid)

                out.append(
                    self._normalize_correction_record(rec, meta)
                )
        except Exception as exc:
            logger.warning(
                "KB corrections read failed (non-fatal): %s", exc
            )

    @staticmethod
    def _normalize_correction_record(
        rec: Dict, meta: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Map a raw record to the canonical output shape."""
        if meta is None:
            meta = rec
        before = rec.get("before") or rec.get("original_lua") or ""
        after = rec.get("after") or rec.get("corrected_lua") or ""
        reason = (
            rec.get("reason")
            or rec.get("diff")
            or rec.get("correction_reason")
            or ""
        )
        recorded_at = (
            rec.get("recorded_at")
            or meta.get("recorded_at")
            or ""
        )
        correction_id = (
            rec.get("correction_id")
            or meta.get("correction_id")
            or ""
        )
        return {
            "before": str(before),
            "after": str(after),
            "reason": str(reason),
            "recorded_at": str(recorded_at),
            "correction_id": str(correction_id),
        }

    async def get_feedback_statistics(self) -> Dict:
        """Get statistics about collected feedback"""
        return {
            **self.statistics,
            'success_rate': self._calculate_success_rate(),
            'most_common_correction_type': await self._get_most_common_correction_type()
        }

    def _calculate_success_rate(self) -> float:
        """Calculate overall success rate from deployments"""
        if self.statistics['deployments_tracked'] == 0:
            return 0.0

        # This would query the knowledge base for successful vs failed deployments
        # For now, return placeholder
        return 0.0  # Implement actual calculation

    async def _get_most_common_correction_type(self) -> str:
        """Get the most common type of user correction"""
        # This would query the knowledge base and count correction types
        # For now, return placeholder
        return 'unknown'  # Implement actual query
