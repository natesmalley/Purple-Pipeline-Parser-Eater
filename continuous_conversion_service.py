#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Continuous Conversion Service

Runs the entire Purple Pipeline Parser Eater system continuously:
- Monitors for new SentinelOne parsers (GitHub sync)
- Automatically converts new parsers when detected
- Provides web UI for user feedback
- Learns from user corrections in real-time
- Deploys approved conversions automatically
"""

import asyncio
import yaml
import logging
import sys
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from utils.config_expansion import expand_environment_variables

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/continuous_service.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class ContinuousConversionService:
    """
    Main service that runs continuously, coordinating:
    - RAG GitHub sync (every 60 min)
    - Automatic conversion of new parsers
    - Web UI for user feedback
    - Learning from feedback
    - Deployment of approved conversions
    """

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = None
        self.is_running = False

        # Components
        self.knowledge_base = None
        self.rag_updater = None
        self.feedback_system = None
        self.web_server = None

        # Queues for async communication
        self.conversion_queue = asyncio.Queue()
        self.feedback_queue = asyncio.Queue()

        # State
        self.pending_conversions: Dict = {}
        self.approved_conversions: List = []
        self.rejected_conversions: List = []
        self.modified_conversions: List = []  # Track modified then approved

        # SDL audit logger (initialized in init)
        self.sdl_audit_logger = None

    def _expand_environment_variables(self, text: str) -> str:
        """
        Expand environment variables in YAML config using ${VAR} or ${VAR:default} syntax.

        This method now delegates to utils.config_expansion for centralized
        environment variable handling across all components.

        See utils.config_expansion.expand_environment_variables for syntax details
        """
        return expand_environment_variables(text, strict=False)

    async def initialize(self) -> None:
        """Initialize all components."""
        logger.info("=" * 70)
        logger.info("CONTINUOUS CONVERSION SERVICE INITIALIZATION")
        logger.info("=" * 70)

        # Load configuration with environment variable expansion
        with open(self.config_path, 'r') as f:
            config_text = f.read()

        # Expand environment variables
        expanded_text = self._expand_environment_variables(config_text)
        self.config = yaml.safe_load(expanded_text)

        # Initialize RAG Knowledge Base
        logger.info("Initializing RAG Knowledge Base...")
        from components.rag_knowledge import RAGKnowledgeBase
        self.knowledge_base = RAGKnowledgeBase(config=self.config)

        if not self.knowledge_base.enabled:
            logger.warning("RAG Knowledge Base not available - continuing without RAG features")

        logger.info("[OK] RAG Knowledge Base initialized")

        # Initialize RAG Auto-Updater (GitHub sync) - optional
        try:
            logger.info("Initializing RAG Auto-Updater...")
            from components.rag_auto_updater_github import RAGAutoUpdaterGitHub
            self.rag_updater = RAGAutoUpdaterGitHub(config=self.config)
            logger.info("[OK] RAG Auto-Updater initialized")
        except Exception as e:
            logger.warning(f"RAG Auto-Updater not available: {e}")
            self.rag_updater = None

        # Initialize Feedback System - optional
        try:
            logger.info("Initializing Feedback System...")
            from components.feedback_system import FeedbackSystem
            self.feedback_system = FeedbackSystem(
                config=self.config,
                knowledge_base=self.knowledge_base
            )
            logger.info("[OK] Feedback System initialized")
        except Exception as e:
            logger.warning(f"Feedback System not available: {e}")
            self.feedback_system = None

        # Initialize SDL Audit Logger - optional
        try:
            logger.info("Initializing SDL Audit Logger...")
            from components.sdl_audit_logger import SDLAuditLogger
            self.sdl_audit_logger = SDLAuditLogger(config=self.config)
            logger.info("[OK] SDL Audit Logger initialized")
        except Exception as e:
            logger.warning(f"SDL Audit Logger not available: {e}")
            self.sdl_audit_logger = None

        # Initialize SDL Logging Handler - optional
        try:
            logger.info("Initializing SDL Logging Handler...")
            from components.sdl_logging_handler import configure_sdl_logging
            self.sdl_logging_handler = configure_sdl_logging(self.config)
            logger.info("[OK] SDL Logging Handler initialized")
        except Exception as e:
            logger.warning(f"SDL Logging Handler not available: {e}")
            self.sdl_logging_handler = None

        # Initialize Web UI Server (will create in next step)
        logger.info("Initializing Web UI Server...")
        from components.web_ui import WebFeedbackServer
        from services.runtime_service import RuntimeService

        self.runtime_service = RuntimeService(self.config)
        self.web_server = WebFeedbackServer(
            config=self.config,
            feedback_queue=self.feedback_queue,
            service=self,
            event_loop=asyncio.get_event_loop(),  # Pass event loop for Flask callbacks
            runtime_service=self.runtime_service,
        )
        logger.info("[OK] Web UI Server initialized")

        logger.info("=" * 70)
        logger.info("INITIALIZATION COMPLETE")
        logger.info("=" * 70)

        return True

    async def start(self) -> None:
        """Start the continuous service."""
        if not await self.initialize():
            logger.error("Initialization failed")
            return

        self.is_running = True
        logger.info("Starting Continuous Conversion Service...")

        # Load historical parsers for Web UI testing (if available)
        # PRODUCTION MODE: Disabled - only process new parsers from GitHub sync
        # TESTING MODE: Uncomment line below to load 10 test parsers on startup
        # await self.load_historical_parsers()

        # Create concurrent tasks
        tasks = [
            asyncio.create_task(self.rag_sync_loop(), name="RAG_Sync"),
            asyncio.create_task(self.conversion_loop(), name="Conversion"),
            asyncio.create_task(self.feedback_loop(), name="Feedback"),
            asyncio.create_task(self.web_server.start(), name="WebUI"),
        ]

        logger.info(f"Started {len(tasks)} concurrent tasks:")
        for task in tasks:
            logger.info(f"  - {task.get_name()}")

        # Wait for all tasks
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Service error: {e}", exc_info=True)
        finally:
            self.is_running = False

    async def rag_sync_loop(self) -> None:
        """Continuously sync RAG with GitHub (every 60 min)."""
        logger.info("RAG Sync Loop started")

        from components.github_scanner import GitHubParserScanner
        github_token = self.config.get('github', {}).get('token')

        async with GitHubParserScanner(github_token=github_token, config=self.config) as scanner:
            while self.is_running:
                try:
                    # Run update cycle
                    update_info = await self.rag_updater.check_for_updates(scanner)

                    stats = update_info['stats']
                    new_parsers = [p for p in update_info['parsers_to_update'] if p['status'] == 'new']

                    logger.info(f"RAG Sync: {stats['new']} new, {stats['updated']} updated")

                    # Apply updates to RAG
                    await self.rag_updater.apply_updates(update_info, self.knowledge_base)

                    # Queue new parsers for conversion
                    for parser in new_parsers:
                        await self.conversion_queue.put({
                            'parser_name': parser['name'],
                            'content': parser['content'],
                            'metadata': parser['metadata'],
                            'timestamp': datetime.now().isoformat()
                        })
                        logger.info(f"Queued for conversion: {parser['name']}")

                    # Wait for configured interval
                    interval = self.config.get('rag_auto_update', {}).get('interval_minutes', 60)
                    logger.info(f"Next RAG sync in {interval} minutes...")
                    await asyncio.sleep(interval * 60)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"RAG sync error: {e}")
                    await asyncio.sleep(300)  # Wait 5 min on error

    async def conversion_loop(self) -> None:
        """Process conversion queue."""
        logger.info("Conversion Loop started")

        while self.is_running:
            parser_info = None
            try:
                # Get parser from queue (wait up to 10 sec)
                try:
                    parser_info = await asyncio.wait_for(
                        self.conversion_queue.get(),
                        timeout=10.0
                    )
                except asyncio.TimeoutError:
                    continue

                parser_name = parser_info['parser_name']
                logger.info(f"Converting parser: {parser_name}")

                # Run conversion (orchestrator)
                result = await self.convert_parser(parser_info)

                # Store for user review
                self.pending_conversions[parser_name] = {
                    'parser_info': parser_info,
                    'conversion_result': result,
                    'status': 'pending_review',
                    'timestamp': datetime.now().isoformat()
                }

                logger.info(f"Conversion complete: {parser_name} → pending user review")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Conversion error: {e}", exc_info=True)
            finally:
                # Mark task as done
                if parser_info is not None:
                    self.conversion_queue.task_done()

    async def feedback_loop(self) -> None:
        """Process user feedback."""
        logger.info("Feedback Loop started")

        while self.is_running:
            feedback = None
            try:
                # Get feedback from queue (FIXED: was .put(), now .get())
                try:
                    feedback = await asyncio.wait_for(
                        self.feedback_queue.get(),
                        timeout=10.0
                    )
                except asyncio.TimeoutError:
                    continue

                parser_name = feedback['parser_name']
                action = feedback['action']  # 'approve', 'reject', 'modify'

                logger.info(f"Received feedback: {parser_name} → {action}")

                if action == 'approve':
                    await self.handle_approval(parser_name, feedback)
                elif action == 'reject':
                    await self.handle_rejection(parser_name, feedback)
                elif action == 'modify':
                    await self.handle_modification(parser_name, feedback)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Feedback error: {e}", exc_info=True)
            finally:
                # Mark task as done
                if feedback is not None:
                    self.feedback_queue.task_done()

    async def convert_parser(self, parser_info: Dict) -> Dict:
        """Run conversion for a single parser"""
        from components.lua_generator import ClaudeLuaGenerator
        import time

        try:
            parser_name = parser_info['parser_name']
            content = parser_info['content']
            metadata = parser_info['metadata']

            logger.info(f"[LUA] Generating LUA code for {parser_name}...")
            start_time = time.time()

            # Create LUA generator (initialized with config, accesses RAG through config)
            lua_gen = ClaudeLuaGenerator(config=self.config)

            # Create parser_analysis dict in the format expected by generate_lua()
            # The analysis should contain the parser's semantic understanding
            parser_analysis = {
                'parser_id': parser_name,
                'content': content,
                'metadata': metadata,
                # Add analysis fields that would normally come from Phase 2
                'fields_extracted': metadata.get('fields_extracted', []),
                'ocsf_classification': metadata.get('ocsf_classification', {}),
                'parser_complexity': metadata.get('parser_complexity', {}),
                'parser_type': metadata.get('parser_type', 'unknown')
            }

            # Generate LUA code using the correct method signature
            lua_result = await lua_gen.generate_lua(
                parser_id=parser_name,
                parser_analysis=parser_analysis,
                ocsf_schema=None  # Optional OCSF schema
            )

            generation_time = time.time() - start_time

            # LuaGenerationResult is returned on success, None on failure
            if lua_result and hasattr(lua_result, 'lua_code'):
                logger.info(f"[OK] Generated LUA for {parser_name} ({generation_time:.1f}s)")
                return {
                    'success': True,
                    'lua_code': lua_result.lua_code,
                    'generation_time': generation_time,
                    'parser_id': lua_result.parser_id,
                    'confidence_score': lua_result.confidence_score if hasattr(lua_result, 'confidence_score') else 0.0
                }
            else:
                error_msg = "LUA generation returned None - check logs for details"
                logger.error(f"[FAIL] LUA generation failed for {parser_name}: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'generation_time': generation_time
                }

        except Exception as e:
            logger.error(f"Conversion error for {parser_info['parser_name']}: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'generation_time': 0
            }

    async def handle_approval(self, parser_name: str, feedback: Dict) -> None:
        """Handle user approval + send to SDL SIEM."""
        conversion = self.pending_conversions.get(parser_name)
        if not conversion:
            return

        logger.info(f"Approved: {parser_name}")

        result = conversion['conversion_result']

        # Send audit event to SDL SIEM for tracking
        if self.sdl_audit_logger:
            await self.sdl_audit_logger.log_approval(
                parser_name=parser_name,
                lua_code=result.get('lua_code', ''),
                generation_time=result.get('generation_time', 0.0),
                confidence_score=result.get('confidence_score', 0.0),
                user_id=feedback.get('user_id', 'web-ui-user')
            )

        # Record success in feedback system
        if self.feedback_system:
            await self.feedback_system.record_lua_generation_success(
                parser_name=parser_name,
                lua_code=result['lua_code'],
                generation_time_sec=result.get('generation_time', 0.0),
                confidence_score=result.get('confidence_score'),
                strategy=result.get('strategy')
            )

        # Deploy to Observo.ai (if configured)
        # await self.deploy_conversion(conversion)

        # Move to approved
        conversion['approval_timestamp'] = datetime.now().isoformat()
        self.approved_conversions.append(conversion)
        del self.pending_conversions[parser_name]
        logger.info(f"[OK] {parser_name} moved to approved list (total: {len(self.approved_conversions)})")

    async def handle_rejection(self, parser_name: str, feedback: Dict) -> None:
        """Handle user rejection + send to SDL SIEM."""
        conversion = self.pending_conversions.get(parser_name)
        if not conversion:
            return

        reason = feedback.get('reason', 'No reason provided')
        retry = feedback.get('retry', False)

        logger.info(f"Rejected: {parser_name} - {reason}")

        result = conversion['conversion_result']

        # Send audit event to SDL SIEM for tracking
        if self.sdl_audit_logger:
            await self.sdl_audit_logger.log_rejection(
                parser_name=parser_name,
                reason=reason,
                retry_requested=retry,
                lua_code=result.get('lua_code'),
                error_details=result.get('error'),
                user_id=feedback.get('user_id', 'web-ui-user')
            )

        # Record failure in feedback system
        if self.feedback_system:
            await self.feedback_system.record_lua_generation_failure(
                parser_name=parser_name,
                error_message=reason,
                attempted_strategy=result.get('strategy', 'unknown'),
                error_type=result.get('error_type', 'user_rejection')
            )

        # Move to rejected
        conversion['rejection_timestamp'] = datetime.now().isoformat()
        conversion['rejection_reason'] = reason
        self.rejected_conversions.append(conversion)
        del self.pending_conversions[parser_name]

        # Optionally: Re-queue with different strategy
        if retry:
            await self.conversion_queue.put(conversion['parser_info'])
            logger.info(f"[RETRY] Re-queued {parser_name} for conversion")

    async def handle_modification(self, parser_name: str, feedback: Dict) -> None:
        """Handle user modification + send to SDL SIEM."""
        conversion = self.pending_conversions.get(parser_name)
        if not conversion:
            return

        original_lua = conversion['conversion_result']['lua_code']
        corrected_lua = feedback['corrected_lua']
        modification_reason = feedback.get('reason', 'User modification')

        logger.info(f"Modified: {parser_name}")

        # Send audit event to SDL SIEM for tracking
        if self.sdl_audit_logger:
            await self.sdl_audit_logger.log_modification(
                parser_name=parser_name,
                original_lua=original_lua,
                modified_lua=corrected_lua,
                modification_reason=modification_reason,
                user_id=feedback.get('user_id', 'web-ui-user')
            )

        # Record correction for learning
        await self.feedback_system.record_lua_correction(
            parser_name=parser_name,
            original_lua=original_lua,
            corrected_lua=corrected_lua,
            correction_reason=modification_reason
        )

        # Update conversion with corrected code
        conversion['conversion_result']['lua_code'] = corrected_lua
        conversion['conversion_result']['original_lua'] = original_lua
        conversion['status'] = 'modified_approved'
        conversion['modification_timestamp'] = datetime.now().isoformat()
        conversion['modification_reason'] = modification_reason

        # Add to BOTH modified list AND approved list
        self.modified_conversions.append(conversion)
        self.approved_conversions.append(conversion)
        del self.pending_conversions[parser_name]

        logger.info(f"[OK] {parser_name} modified and approved (modified: {len(self.modified_conversions)}, approved: {len(self.approved_conversions)})")

    async def load_historical_parsers(self) -> None:
        """Load historical parsers from output directory for Web UI testing."""
        import json

        historical_file = Path("output/02_analyzed_parsers.json")
        if not historical_file.exists():
            logger.info("No historical parsers found (02_analyzed_parsers.json)")
            return

        try:
            with open(historical_file, 'r', encoding='utf-8') as f:
                analyzed_parsers = json.load(f)

            # Handle both dict and list formats
            if isinstance(analyzed_parsers, list):
                parsers_to_load = analyzed_parsers[:10]  # First 10 parsers
            else:
                parsers_to_load = list(analyzed_parsers.values())[:10]

            logger.info(f"Loading {len(parsers_to_load)} historical parsers for Web UI testing...")

            for parser_data in parsers_to_load:
                parser_name = parser_data.get('parser_name', parser_data.get('name', 'unknown'))
                await self.conversion_queue.put({
                    'parser_name': parser_name,
                    'content': parser_data.get('content', ''),
                    'metadata': parser_data.get('metadata', {}),
                    'timestamp': datetime.now().isoformat(),
                    'historical': True  # Flag to indicate this is historical data
                })
                logger.info(f"Queued historical parser: {parser_name}")

            logger.info(f"[OK] Loaded {len(parsers_to_load)} historical parsers for conversion")
        except Exception as e:
            logger.warning(f"Could not load historical parsers: {e}")

    def get_status(self) -> Dict:
        """Get service status including SDL audit stats"""
        return {
            'is_running': self.is_running,
            'pending_conversions': len(self.pending_conversions),
            'approved_conversions': len(self.approved_conversions),
            'rejected_conversions': len(self.rejected_conversions),
            'modified_conversions': len(self.modified_conversions),
            'queue_size': self.conversion_queue.qsize(),
            'rag_status': self.rag_updater.get_status() if self.rag_updater else {},
            'sdl_audit_stats': self.sdl_audit_logger.get_statistics() if self.sdl_audit_logger else {}
        }

    def get_runtime_status(self) -> Dict:
        if hasattr(self, "runtime_service") and self.runtime_service:
            return self.runtime_service.get_runtime_status()
        return {
            "metrics": {},
            "reload_requests": {},
            "pending_promotions": {},
        }

    def request_runtime_reload(self, parser_id: str) -> bool:
        if hasattr(self, "runtime_service") and self.runtime_service:
            return self.runtime_service.request_runtime_reload(parser_id)
        return False

    def pop_runtime_reload(self, parser_id: str) -> Optional[str]:
        if hasattr(self, "runtime_service") and self.runtime_service:
            return self.runtime_service.pop_reload_request(parser_id)
        return None

    def request_canary_promotion(self, parser_id: str) -> bool:
        if hasattr(self, "runtime_service") and self.runtime_service:
            return self.runtime_service.request_canary_promotion(parser_id)
        return False

    def pop_canary_promotion(self, parser_id: str) -> Optional[str]:
        if hasattr(self, "runtime_service") and self.runtime_service:
            return self.runtime_service.pop_canary_promotion(parser_id)
        return None


async def main():
    """Main entry point"""
    print("\n" + "=" * 70)
    print("CONTINUOUS CONVERSION SERVICE")
    print("=" * 70)
    print("\nThis service runs continuously and:")
    print("  • Syncs new parsers from GitHub every 60 minutes")
    print("  • Automatically converts new parsers")
    print("  • Provides web UI for user feedback")
    print("  • Learns from your corrections in real-time")
    print("  • Deploys approved conversions")
    print("\nWeb UI will be available at: http://localhost:8080")
    print("\nPress Ctrl+C to stop the service.")
    print("=" * 70 + "\n")

    # Find config file
    config_path = Path("../config.yaml")
    if not config_path.exists():
        config_path = Path("config.yaml")

    if not config_path.exists():
        print("ERROR: config.yaml not found!")
        return 1

    # Create service
    service = ContinuousConversionService(config_path)

    # Start service
    try:
        await service.start()
    except KeyboardInterrupt:
        print("\nShutdown requested...")

    print("\nContinuous Conversion Service stopped.\n")
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nService interrupted by user")
        sys.exit(0)
