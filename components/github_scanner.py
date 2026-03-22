"""
GitHub Parser Scanner for Purple Pipeline Parser Eater
Scans SentinelOne ai-siem repository for parser configurations
"""
import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import base64
import json
import yaml
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential
import re

# Use absolute imports for proper module execution
try:
    from utils.error_handler import ParserScanError, RateLimiter, handle_api_errors
except ImportError:
    from ..utils.error_handler import ParserScanError, RateLimiter, handle_api_errors


logger = logging.getLogger(__name__)


class GitHubParserScanner:
    """Scan and retrieve SentinelOne parsers from GitHub"""

    def __init__(self, github_token: Optional[str] = None, config: Optional[Dict] = None):
        self.base_url = "https://api.github.com/repos/Sentinel-One/ai-siem"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Purple-Pipeline-Parser-Eater/1.0"
        }

        # Detect mock mode for dry-run
        self.mock_mode = False
        if not github_token or github_token in ("your-github-token-here", "dry-run-mode"):
            self.mock_mode = True
            logger.info("[MOCK MODE] GitHub scanner running in mock mode (no API calls)")
        elif github_token:
            self.headers["Authorization"] = f"token {github_token}"

        self.config = config or {}
        self.rate_limiter = RateLimiter(
            calls_per_second=1.0 / self.config.get("github", {}).get("rate_limit_delay", 1.0)
        )
        self.session: Optional[aiohttp.ClientSession] = None

        # Initialize Anthropic client for Claude AI JSON fixing (if configured)
        self.claude_client = None
        anthropic_key = self.config.get("anthropic", {}).get("api_key")
        if anthropic_key and anthropic_key != "your-anthropic-api-key-here":
            try:
                from anthropic import Anthropic
                self.claude_client = Anthropic(api_key=anthropic_key)
                logger.info("[CLAUDE] Claude AI JSON repair enabled")
            except ImportError:
                logger.warning("[CLAUDE] Anthropic library not available - Claude JSON repair disabled")

        self.statistics = {
            "total_scanned": 0,
            "community_parsers": 0,
            "sentinelone_parsers": 0,
            "claude_json_fixes": 0,
            "claude_multipass_fixes": 0,
            "heuristic_fixes": 0,
            "errors": [],
            "scan_start": None,
            "scan_end": None,
            "mock_mode": self.mock_mode
        }

    async def __aenter__(self):
        """Async context manager entry - create session with connection pooling"""
        # Create TCP connector with connection pooling
        # limit: max total connections
        # limit_per_host: max connections to single host
        connector = aiohttp.TCPConnector(
            limit=100,           # Max total connections
            limit_per_host=10,   # Max per host
            ttl_dns_cache=300    # DNS cache TTL in seconds
        )
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            connector=connector
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - properly close session"""
        if self.session:
            await self.session.close()

    @handle_api_errors("GitHub")
    async def scan_parsers(self) -> List[Dict]:
        """
        Scan both community and sentinelone parser directories
        Returns list of parser configurations with metadata
        """
        logger.info("Starting GitHub parser scan for Purple Pipeline Parser Eater")
        self.statistics["scan_start"] = datetime.now().isoformat()

        # MOCK MODE: Return synthetic parser data for dry-run
        if self.mock_mode:
            logger.info("[MOCK MODE] Returning synthetic parser data for dry-run testing")
            mock_parsers = self._generate_mock_parsers()
            self.statistics["total_scanned"] = len(mock_parsers)
            self.statistics["community_parsers"] = len(mock_parsers)
            self.statistics["scan_end"] = datetime.now().isoformat()
            logger.info(f"[MOCK MODE] Generated {len(mock_parsers)} mock parsers")
            return mock_parsers

        all_parsers = []

        try:
            # Scan community parsers (148+)
            logger.info("Scanning community parsers directory...")
            community_parsers = await self._scan_directory("parsers/community")
            all_parsers.extend(community_parsers)
            self.statistics["community_parsers"] = len(community_parsers)
            logger.info(f"Found {len(community_parsers)} community parsers")

            # Scan SentinelOne parsers (17+)
            logger.info("Scanning SentinelOne parsers directory...")
            sentinelone_parsers = await self._scan_directory("parsers/sentinelone")
            all_parsers.extend(sentinelone_parsers)
            self.statistics["sentinelone_parsers"] = len(sentinelone_parsers)
            logger.info(f"Found {len(sentinelone_parsers)} SentinelOne parsers")

            self.statistics["total_scanned"] = len(all_parsers)
            self.statistics["scan_end"] = datetime.now().isoformat()

            logger.info(f"[OK] Scan complete: {len(all_parsers)} total parsers found")
            return all_parsers

        except Exception as e:
            logger.error(f"Failed to scan parsers: {e}")
            self.statistics["errors"].append(str(e))
            raise ParserScanError(f"Parser scan failed: {e}")

    async def _scan_directory(self, path: str) -> List[Dict]:
        """Scan a specific directory for parser configurations"""
        await self.rate_limiter.wait()

        url = f"{self.base_url}/contents/{path}"
        logger.debug(f"Scanning directory: {url}")

        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise ParserScanError(f"GitHub API returned {response.status}")

                contents = await response.json()

            parsers = []
            parser_dirs = [item for item in contents if item["type"] == "dir"]

            for parser_dir in parser_dirs:
                parser_info = await self._fetch_parser_files(parser_dir["path"], parser_dir["name"])
                if parser_info:
                    parsers.append(parser_info)

            return parsers

        except aiohttp.ClientError as e:
            logger.error(f"HTTP error scanning directory {path}: {e}")
            raise ParserScanError(f"Failed to scan directory {path}: {e}")

    async def _fetch_parser_files(self, parser_path: str, parser_name: str) -> Optional[Dict]:
        """Fetch parser configuration and metadata files"""
        await self.rate_limiter.wait()

        try:
            # Fetch directory contents
            url = f"{self.base_url}/contents/{parser_path}"
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"Failed to fetch parser directory {parser_path}")
                    return None

                contents = await response.json()

            # Strategy 4: Flexible file detection
            # Find .conf, .json, .yaml files and metadata.yaml
            conf_file = None
            metadata_file = None

            for item in contents:
                # Check for configuration files (priority order)
                if item["name"].endswith(".conf") and not conf_file:
                    conf_file = item
                elif item["name"].endswith(".json") and not conf_file:
                    conf_file = item
                elif item["name"].endswith(".yaml") and not conf_file:
                    conf_file = item
                # Check for metadata file
                elif item["name"] == "metadata.yaml":
                    metadata_file = item

            if not conf_file:
                logger.warning(f"No config file (.conf/.json/.yaml) found for {parser_name}")
                return None

            # Fetch parser configuration
            parser_config = await self._fetch_file_content(conf_file["download_url"])
            if not parser_config:
                return None

            # Fetch metadata if available
            metadata = {}
            if metadata_file:
                metadata_content = await self._fetch_file_content(metadata_file["download_url"])
                if metadata_content:
                    try:
                        metadata = yaml.safe_load(metadata_content)
                    except yaml.YAMLError as e:
                        logger.warning(f"Failed to parse metadata for {parser_name}: {e}")

            # Parse JSON using 4-strategy approach
            if isinstance(parser_config, str):
                parsed_config = self._parse_json_with_strategies(
                    parser_config, parser_name
                )
                if not parsed_config:
                    logger.error(f"All parsing strategies failed: {parser_name}")
                    return None
            else:
                parsed_config = parser_config

            return {
                "parser_id": parser_name,
                "parser_name": parser_name,
                "source_path": parser_path,
                "config_file": conf_file["name"],
                "config": parsed_config,
                "metadata": metadata,
                "source_type": "community" if "community" in parser_path else "sentinelone",
                "fetched_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to fetch parser files for {parser_name}: {e}")
            self.statistics["errors"].append(f"Parser {parser_name}: {str(e)}")
            return None

    async def _fetch_file_content(self, download_url: str) -> Optional[str]:
        """Fetch file content from GitHub"""
        await self.rate_limiter.wait()

        try:
            async with self.session.get(download_url) as response:
                if response.status != 200:
                    logger.warning(f"Failed to fetch file from {download_url}")
                    return None

                content = await response.text()
                return content

        except Exception as e:
            logger.error(f"Failed to fetch file content: {e}")
            return None

    def _fix_json5_with_claude(self, json5_string: str, parser_name: str,
                                aggressive: bool = False) -> Optional[str]:
        """
        Strategy 1: Use Claude AI to convert JSON5 to valid JSON

        Args:
            json5_string: The JSON5 content to fix
            parser_name: Parser name for logging
            aggressive: Use more aggressive repair instructions

        Returns:
            Fixed JSON string or None if repair failed
        """
        if not self.claude_client:
            return None

        try:
            # Construct prompt based on aggressiveness level
            if aggressive:
                prompt = f"""CRITICAL JSON5 REPAIR TASK:
This JSON5 has severe structural errors. Fix ALL issues:
- Add missing commas between properties
- Add missing closing brackets/braces
- Quote all unquoted keys
- Remove ALL comments (// and /* */)
- Remove trailing commas
- Escape special characters in strings
- Fix malformed strings

Return ONLY valid JSON, no markdown, no explanations.

JSON5:
```
{json5_string[:3000]}
```"""
            else:
                prompt = f"""Convert this JSON5 to valid JSON.
Remove comments, quote all keys, remove trailing commas.
Return ONLY the valid JSON, no explanations.

JSON5:
```
{json5_string[:3000]}
```"""

            response = self.claude_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )

            json_fixed = response.content[0].text.strip()

            # Remove markdown code blocks if present
            if json_fixed.startswith("```"):
                json_fixed = re.sub(r'^```(?:json)?\n', '', json_fixed)
                json_fixed = re.sub(r'\n```$', '', json_fixed)

            # Validate the fixed JSON
            json.loads(json_fixed)

            if aggressive:
                self.statistics["claude_multipass_fixes"] += 1
                logger.debug(f"[CLAUDE-AGGRESSIVE] Fixed {parser_name}")
            else:
                self.statistics["claude_json_fixes"] += 1
                logger.debug(f"[CLAUDE] Fixed {parser_name}")

            return json_fixed

        except Exception as e:
            logger.debug(f"[CLAUDE] Repair failed for {parser_name}: {e}")
            return None

    def _multipass_repair(self, json5_string: str,
                          parser_name: str) -> Optional[str]:
        """
        Strategy 2: Multi-pass Claude AI repair with escalating aggression

        Attempts:
        1. Standard Claude repair
        2. Aggressive Claude repair
        3. Aggressive repair on truncated/cleaned input
        """
        # Pass 1: Standard repair
        result = self._fix_json5_with_claude(json5_string, parser_name,
                                              aggressive=False)
        if result:
            return result

        # Pass 2: Aggressive repair
        result = self._fix_json5_with_claude(json5_string, parser_name,
                                              aggressive=True)
        if result:
            return result

        # Pass 3: Pre-clean and aggressive repair
        try:
            # Remove obvious problematic patterns
            cleaned = json5_string
            cleaned = re.sub(r'//.*?$', '', cleaned, flags=re.MULTILINE)
            cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)

            result = self._fix_json5_with_claude(cleaned, parser_name,
                                                  aggressive=True)
            if result:
                return result
        except Exception as e:
            logger.debug(f"[MULTIPASS] Pre-clean failed for {parser_name}")

        return None

    def _heuristic_repair(self, json5_string: str,
                          parser_name: str) -> Optional[str]:
        """
        Strategy 3: Heuristic programmatic repair for common issues

        Handles:
        - Missing commas between properties
        - Unquoted keys
        - Trailing commas
        - Basic comment removal
        """
        try:
            repaired = json5_string

            # Remove single-line comments
            repaired = re.sub(r'//.*?$', '', repaired, flags=re.MULTILINE)

            # Remove multi-line comments
            repaired = re.sub(r'/\*.*?\*/', '', repaired, flags=re.DOTALL)

            # Quote unquoted keys (basic pattern)
            repaired = re.sub(r'(\n\s*)(\w+)(\s*:)',
                              r'\1"\2"\3', repaired)

            # Remove trailing commas
            repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)

            # Attempt to parse
            parsed = json.loads(repaired)
            self.statistics["heuristic_fixes"] += 1
            logger.debug(f"[HEURISTIC] Fixed {parser_name}")
            return repaired

        except Exception as e:
            logger.debug(f"[HEURISTIC] Repair failed for {parser_name}")
            return None

    def _parse_json_with_strategies(self, content: str,
                                     parser_name: str) -> Optional[Dict]:
        """
        4-Strategy JSON parsing with cascading fallback

        Strategy 1: Standard JSON parsing
        Strategy 2: Claude AI single-pass repair
        Strategy 3: Claude AI multi-pass repair
        Strategy 4: Heuristic programmatic repair

        Returns parsed dict or None
        """
        # Strategy 1: Try standard JSON parsing first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.debug(f"[STRATEGY-1] Standard JSON failed: {parser_name}")

        # Strategy 2: Claude AI single-pass repair
        if self.claude_client:
            fixed = self._fix_json5_with_claude(content, parser_name,
                                                 aggressive=False)
            if fixed:
                try:
                    return json.loads(fixed)
                except json.JSONDecodeError:
                    pass

        # Strategy 3: Multi-pass Claude AI repair
        if self.claude_client:
            fixed = self._multipass_repair(content, parser_name)
            if fixed:
                try:
                    return json.loads(fixed)
                except json.JSONDecodeError:
                    pass

        # Strategy 4: Heuristic repair
        fixed = self._heuristic_repair(content, parser_name)
        if fixed:
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

        # All strategies failed
        logger.debug(f"[ALL-STRATEGIES-FAILED] {parser_name}")
        return None

    def get_statistics(self) -> Dict:
        """Get scan statistics"""
        return self.statistics

    async def validate_parser(self, parser: Dict) -> bool:
        """Validate parser configuration structure"""
        try:
            config = parser.get("config", {})

            # Check required fields
            required_fields = ["attributes", "formats", "mappings"]
            for field in required_fields:
                if field not in config:
                    logger.warning(f"Parser {parser['parser_id']} missing required field: {field}")
                    return False

            # Validate mappings structure
            mappings = config.get("mappings", {})
            if not mappings.get("mappings"):
                logger.warning(f"Parser {parser['parser_id']} has no mapping rules")
                return False

            return True

        except Exception as e:
            logger.error(f"Validation error for parser {parser.get('parser_id', 'unknown')}: {e}")
            return False

    async def fetch_parser_by_name(self, parser_name: str, source_type: str = "community") -> Optional[Dict]:
        """Fetch a specific parser by name"""
        path = f"parsers/{source_type}/{parser_name}"
        return await self._fetch_parser_files(path, parser_name)

    async def batch_fetch_parsers(self, parser_names: List[str], batch_size: int = 10) -> List[Dict]:
        """Fetch multiple parsers in batches"""
        parsers = []

        for i in range(0, len(parser_names), batch_size):
            batch = parser_names[i:i + batch_size]
            batch_tasks = [self.fetch_parser_by_name(name) for name in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch fetch error: {result}")
                elif result:
                    parsers.append(result)

        return parsers

    def _generate_mock_parsers(self) -> List[Dict]:
        """
        Generate synthetic parser data for dry-run mode
        Returns realistic parser structures for downstream processing
        """
        mock_parsers = [
            {
                "parser_id": "mock-windows-security",
                "parser_name": "mock-windows-security",
                "source_type": "community",
                "repository": "sentinel-one/ai-siem (mock)",
                "path": "parsers/community/mock-windows-security",
                "config": {
                    "attributes": {
                        "dataSource": {
                            "vendor": "Microsoft",
                            "product": "Windows Security Event Log"
                        }
                    },
                    "formats": [
                        {
                            "format": "json"
                        }
                    ],
                    "mappings": {
                        "mappings": [
                            {
                                "name": "event_id",
                                "type": "long"
                            },
                            {
                                "name": "timestamp",
                                "type": "date"
                            },
                            {
                                "name": "user_name",
                                "type": "keyword"
                            },
                            {
                                "name": "source_ip",
                                "type": "ip"
                            },
                            {
                                "name": "action",
                                "type": "keyword"
                            }
                        ]
                    }
                },
                "metadata": {
                    "description": "Mock Windows Security Event Log parser for testing",
                    "version": "1.0.0",
                    "category": "operating_system",
                    "log_type": "authentication"
                },
                "sample_events": [
                    {
                        "event_id": 4624,
                        "timestamp": "2025-10-09T00:00:00Z",
                        "user_name": "admin",
                        "source_ip": "192.168.1.100",
                        "action": "login_success"
                    }
                ],
                "fetched_at": datetime.now().isoformat()
            },
            {
                "parser_id": "mock-linux-syslog",
                "parser_name": "mock-linux-syslog",
                "source_type": "community",
                "repository": "sentinel-one/ai-siem (mock)",
                "path": "parsers/community/mock-linux-syslog",
                "config": {
                    "attributes": {
                        "dataSource": {
                            "vendor": "Linux",
                            "product": "Syslog"
                        }
                    },
                    "formats": [
                        {
                            "format": "syslog"
                        }
                    ],
                    "mappings": {
                        "mappings": [
                            {
                                "name": "timestamp",
                                "type": "date"
                            },
                            {
                                "name": "hostname",
                                "type": "keyword"
                            },
                            {
                                "name": "process",
                                "type": "keyword"
                            },
                            {
                                "name": "message",
                                "type": "text"
                            },
                            {
                                "name": "severity",
                                "type": "keyword"
                            }
                        ]
                    }
                },
                "metadata": {
                    "description": "Mock Linux Syslog parser for testing",
                    "version": "1.0.0",
                    "category": "operating_system",
                    "log_type": "system"
                },
                "sample_events": [
                    {
                        "timestamp": "2025-10-09T00:00:00Z",
                        "hostname": "webserver01",
                        "process": "sshd",
                        "message": "Accepted publickey for user from 10.0.0.1",
                        "severity": "info"
                    }
                ],
                "fetched_at": datetime.now().isoformat()
            }
        ]

        logger.info(f"[MOCK MODE] Created {len(mock_parsers)} synthetic parsers")
        return mock_parsers