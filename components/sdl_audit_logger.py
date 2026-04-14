"""
SDL Audit Logger - Send all Web UI actions to SentinelOne Security Data Lake

This component logs ALL user actions (approve, modify, reject) to the SDL
for comprehensive audit tracking and compliance purposes.

Audit events include:
- Action type (approve/modify/reject)
- Parser details
- Timestamps
- User feedback/reasons
- Code modifications
- All syslog-relevant metadata
"""

import asyncio
import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
import socket
import os

logger = logging.getLogger(__name__)


class SDLAuditLogger:
    """
    Audit logger that sends all Web UI actions to SentinelOne SDL

    Uses the Observo.ai add events API to send structured audit logs
    that can be ingested by SentinelOne SDL SIEM for tracking and compliance.
    """

    def __init__(self, config: Dict):
        """Initialize SDL audit logger"""
        self.config = config

        # SentinelOne SDL API configuration
        sdl_config = config.get("sentinelone_sdl", {})
        self.api_url = sdl_config.get("api_url", "https://xdr.us1.sentinelone.net/api/addEvents")
        self.api_key = sdl_config.get("api_key")
        self.enabled = sdl_config.get("audit_logging_enabled", True)
        self.batch_size = sdl_config.get("batch_size", 10)
        self.retry_attempts = sdl_config.get("retry_attempts", 3)

        # Generate unique session ID for this service instance
        import uuid
        self.session_id = f"pppe-{uuid.uuid4().hex[:16]}"

        # Audit log metadata
        self.hostname = socket.gethostname()
        self.service_name = "purple-pipeline-parser-eater"
        self.facility = "local0"  # Syslog facility

        # Statistics
        self.events_sent = 0
        self.events_failed = 0

        if not self.api_key:
            logger.warning("[SDL AUDIT] No Observo API key - audit logging to SDL disabled")
            self.enabled = False

        if self.enabled:
            logger.info(f"[SDL AUDIT] Initialized - sending audit events to {self.api_url}")
        else:
            logger.info("[SDL AUDIT] Disabled - events will be logged locally only")

    async def log_approval(
        self,
        parser_name: str,
        lua_code: str,
        generation_time: float,
        confidence_score: float = 0.0,
        user_id: str = "web-ui-user"
    ):
        """
        Log parser approval to SDL

        Args:
            parser_name: Name of the parser that was approved
            lua_code: The LUA code that was approved
            generation_time: Time taken to generate (seconds)
            confidence_score: AI confidence score
            user_id: ID of user who approved
        """
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "hostname": self.hostname,
            "service": self.service_name,
            "facility": self.facility,
            "severity": "info",
            "message": f"Parser approved: {parser_name}",
            "event_type": "parser_approval",
            "parser_name": parser_name,
            "action": "approve",
            "user_id": user_id,
            "generation_time_sec": generation_time,
            "confidence_score": confidence_score,
            "lua_code_length": len(lua_code),
            "lua_code_hash": self._hash_code(lua_code),
            "status": "success"
        }

        await self._send_audit_event(event)
        logger.info(f"[SDL AUDIT] Logged approval: {parser_name}")

    async def log_rejection(
        self,
        parser_name: str,
        reason: str,
        retry_requested: bool,
        lua_code: Optional[str] = None,
        error_details: Optional[str] = None,
        user_id: str = "web-ui-user"
    ):
        """
        Log parser rejection to SDL

        Args:
            parser_name: Name of the parser that was rejected
            reason: User-provided reason for rejection
            retry_requested: Whether user requested retry
            lua_code: The rejected LUA code (optional)
            error_details: Technical error details (optional)
            user_id: ID of user who rejected
        """
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "hostname": self.hostname,
            "service": self.service_name,
            "facility": self.facility,
            "severity": "warning",
            "message": f"Parser rejected: {parser_name} - {reason}",
            "event_type": "parser_rejection",
            "parser_name": parser_name,
            "action": "reject",
            "user_id": user_id,
            "rejection_reason": reason,
            "retry_requested": retry_requested,
            "error_details": error_details,
            "status": "rejected"
        }

        if lua_code:
            event["lua_code_length"] = len(lua_code)
            event["lua_code_hash"] = self._hash_code(lua_code)

        await self._send_audit_event(event)
        logger.info(f"[SDL AUDIT] Logged rejection: {parser_name}")

    async def log_modification(
        self,
        parser_name: str,
        original_lua: str,
        modified_lua: str,
        modification_reason: Optional[str] = None,
        user_id: str = "web-ui-user"
    ):
        """
        Log parser modification to SDL

        Args:
            parser_name: Name of the parser that was modified
            original_lua: Original LUA code
            modified_lua: User-modified LUA code
            modification_reason: Reason for modification (optional)
            user_id: ID of user who modified
        """
        # Calculate diff statistics
        original_lines = original_lua.split('\n')
        modified_lines = modified_lua.split('\n')

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "hostname": self.hostname,
            "service": self.service_name,
            "facility": self.facility,
            "severity": "notice",
            "message": f"Parser modified: {parser_name}",
            "event_type": "parser_modification",
            "parser_name": parser_name,
            "action": "modify",
            "user_id": user_id,
            "modification_reason": modification_reason,
            "original_lua_hash": self._hash_code(original_lua),
            "modified_lua_hash": self._hash_code(modified_lua),
            "original_line_count": len(original_lines),
            "modified_line_count": len(modified_lines),
            "lines_changed": abs(len(modified_lines) - len(original_lines)),
            "status": "modified"
        }

        await self._send_audit_event(event)
        logger.info(f"[SDL AUDIT] Logged modification: {parser_name}")

    async def log_deployment(
        self,
        parser_name: str,
        pipeline_id: str,
        deployment_status: str,
        observo_response: Optional[Dict] = None
    ):
        """
        Log parser deployment to SDL

        Args:
            parser_name: Name of the parser deployed
            pipeline_id: Observo pipeline ID
            deployment_status: success/failed
            observo_response: Full Observo API response
        """
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "hostname": self.hostname,
            "service": self.service_name,
            "facility": self.facility,
            "severity": "info" if deployment_status == "success" else "error",
            "message": f"Parser deployed: {parser_name} → {pipeline_id}",
            "event_type": "parser_deployment",
            "parser_name": parser_name,
            "action": "deploy",
            "pipeline_id": pipeline_id,
            "deployment_status": deployment_status,
            "status": deployment_status
        }

        if observo_response:
            event["observo_response"] = json.dumps(observo_response)

        await self._send_audit_event(event)
        logger.info(f"[SDL AUDIT] Logged deployment: {parser_name} → {pipeline_id}")

    async def _send_audit_event(self, event: Dict):
        """
        Send audit event to SentinelOne SDL /addEvents API

        Args:
            event: Structured event dictionary
        """
        if not self.enabled:
            # Log locally only
            logger.debug(f"[SDL AUDIT] (local only) {event['event_type']}: {event['message']}")
            return

        try:
            import httpx
            import time

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # Convert timestamp to nanoseconds since Unix epoch (required by SDL)
            # Event timestamp is ISO format, convert to nanoseconds
            from datetime import datetime
            dt = datetime.fromisoformat(event["timestamp"].replace('Z', '+00:00'))
            ts_nanos = str(int(dt.timestamp() * 1_000_000_000))

            # Map severity to SDL format (0-6)
            severity_map = {
                "debug": 1,
                "info": 2,
                "notice": 3,
                "warning": 4,
                "error": 5,
                "critical": 6
            }
            sev = severity_map.get(event.get("severity", "info"), 2)

            # Build SDL event in correct format
            sdl_event = {
                "ts": ts_nanos,
                "sev": sev,
                "attrs": {
                    "message": event["message"],
                    "event_type": event["event_type"],
                    "hostname": event["hostname"],
                    "service": self.service_name,
                    "facility": event["facility"],
                    # Include all other event fields as attributes
                    **{k: str(v) if v is not None else "" for k, v in event.items() if k not in [
                        "timestamp", "message", "event_type", "hostname", "service",
                        "facility", "severity"
                    ]}
                }
            }

            # SDL /addEvents API payload format
            payload = {
                "token": self.api_key,  # Can be in header OR body
                "session": self.session_id,  # Unique session identifier
                "sessionInfo": {
                    "serverHost": self.hostname,
                    "application": self.service_name
                },
                "events": [sdl_event]
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.api_url, json=payload, headers=headers)

                if response.status_code == 200:
                    self.events_sent += 1
                    resp_data = response.json()
                    logger.info(
                        f"[SDL AUDIT] ✓ Event sent to SentinelOne SDL: {event['event_type']} - "
                        f"{event.get('parser_name')} (charged: {resp_data.get('bytesCharged', 0)} bytes)"
                    )
                else:
                    self.events_failed += 1
                    logger.error(
                        f"[SDL AUDIT] ✗ Failed to send event: "
                        f"HTTP {response.status_code} - {response.text[:500]}"
                    )

        except Exception as e:
            self.events_failed += 1
            logger.error(f"[SDL AUDIT] Error sending audit event: {e}", exc_info=True)
            # Log locally as fallback
            logger.info(f"[SDL AUDIT FALLBACK] {json.dumps(event, indent=2)}")

    def _hash_code(self, code: str) -> str:
        """Generate SHA256 hash of code for tracking"""
        import hashlib
        return hashlib.sha256(code.encode('utf-8')).hexdigest()[:16]

    def get_statistics(self) -> Dict:
        """Get audit logging statistics"""
        return {
            "events_sent": self.events_sent,
            "events_failed": self.events_failed,
            "success_rate": (
                self.events_sent / (self.events_sent + self.events_failed)
                if (self.events_sent + self.events_failed) > 0
                else 0.0
            ),
            "enabled": self.enabled
        }
