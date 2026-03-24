"""
Claude GitHub Automation for Purple Pipeline Parser Eater
Automated repository management with intelligent commit messages
"""
import asyncio
import aiohttp
import logging
from typing import Dict, Optional, List
from datetime import datetime
import json
import base64
from anthropic import AsyncAnthropic

# Use absolute imports for proper module execution
try:
    from utils.error_handler import RateLimiter
except ImportError:
    from ..utils.error_handler import RateLimiter


logger = logging.getLogger(__name__)


class ClaudeGitHubAutomation:
    """Automated GitHub repository management with Claude-generated commits"""

    def __init__(self, config: Dict, claude_client: Optional[AsyncAnthropic] = None):
        self.config = config
        github_config = config.get("github", {})

        self.token = github_config.get("token")
        # FIXED: Check for both placeholder and dry-run-mode
        if not self.token or self.token in {"your-github-token-here", "dry-run-mode"}:
            logger.warning("GitHub token not configured - running in mock mode")
            self.mock_mode = True
        else:
            self.mock_mode = False

        self.repo_owner = github_config.get("target_repo_owner", "your-github-username")
        self.repo_name = github_config.get("target_repo_name", "observo-pipelines")

        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Purple-Pipeline-Parser-Eater/1.0"
        }

        self.claude = claude_client
        self.rate_limiter = RateLimiter(
            calls_per_second=1.0 / github_config.get("rate_limit_delay", 1.0)
        )

        self.session: Optional[aiohttp.ClientSession] = None
        self.statistics = {
            "files_uploaded": 0,
            "commits_created": 0,
            "errors": []
        }

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def upload_pipeline_files(
        self,
        parser_id: str,
        lua_code: str,
        documentation: str,
        deployment_result: Dict,
        parser_info: Dict
    ) -> Dict:
        """
        Upload pipeline files to GitHub repository with intelligent organization
        """
        logger.info(f"[UPLOAD] Uploading files for pipeline: {parser_id}")

        await self.rate_limiter.wait()

        try:
            # Generate professional commit message
            commit_message = await self._generate_commit_message(deployment_result, parser_info)

            # Prepare files to upload
            files_to_upload = self._prepare_pipeline_files(
                parser_id,
                lua_code,
                documentation,
                deployment_result,
                parser_info
            )

            # Upload files
            if self.mock_mode:
                logger.info(f"[MOCK MODE] Would upload {len(files_to_upload)} files for {parser_id}")
                result = self._mock_upload_response(parser_id, files_to_upload, commit_message)
            else:
                result = await self._upload_files(files_to_upload, commit_message, parser_info)

            self.statistics["files_uploaded"] += len(files_to_upload)
            self.statistics["commits_created"] += 1

            logger.info(f"[OK] Successfully uploaded {len(files_to_upload)} files for {parser_id}")
            return result

        except Exception as e:
            logger.error(f"Failed to upload files for {parser_id}: {e}")
            self.statistics["errors"].append(f"{parser_id}: {str(e)}")
            raise

    def _prepare_pipeline_files(
        self,
        parser_id: str,
        lua_code: str,
        documentation: str,
        deployment_result: Dict,
        parser_info: Dict
    ) -> List[Dict]:
        """Prepare files for upload with proper organization"""
        source_type = parser_info.get("source_type", "community")
        ocsf_class = parser_info.get("ocsf_classification", {}).get("class_name", "unknown")

        # Sanitize names for file paths
        safe_parser_id = parser_id.replace(" ", "_").replace("/", "-")
        safe_ocsf_class = ocsf_class.replace(" ", "_").lower()

        # Base path: source_type/ocsf_class/parser_id/
        base_path = f"pipelines/{source_type}/{safe_ocsf_class}/{safe_parser_id}"

        files = [
            {
                "path": f"{base_path}/transform.lua",
                "content": lua_code,
                "description": "LUA transformation function"
            },
            {
                "path": f"{base_path}/README.md",
                "content": documentation,
                "description": "Pipeline documentation"
            },
            {
                "path": f"{base_path}/config.json",
                "content": json.dumps(deployment_result.get("configuration", {}), indent=2),
                "description": "Observo.ai pipeline configuration"
            },
            {
                "path": f"{base_path}/metadata.json",
                "content": json.dumps({
                    "parser_id": parser_id,
                    "source_type": source_type,
                    "source_path": parser_info.get("source_path", ""),
                    "ocsf_classification": parser_info.get("ocsf_classification", {}),
                    "parser_complexity": parser_info.get("parser_complexity", {}),
                    "performance_characteristics": parser_info.get("performance_characteristics", {}),
                    "deployment": {
                        "pipeline_id": deployment_result.get("pipeline_id"),
                        "status": deployment_result.get("status"),
                        "deployed_at": deployment_result.get("deployment_time")
                    },
                    "conversion": {
                        "tool": "Purple-Pipeline-Parser-Eater",
                        "version": "1.0.0",
                        "converted_at": datetime.now().isoformat()
                    }
                }, indent=2),
                "description": "Parser metadata and conversion info"
            }
        ]

        return files

    async def _generate_commit_message(self, deployment_result: Dict, parser_info: Dict) -> str:
        """Generate professional commit message using Claude"""
        if not self.claude:
            return self._default_commit_message(parser_info)

        parser_id = parser_info.get("parser_id", "unknown")
        source_type = parser_info.get("source_type", "unknown")
        ocsf_class = parser_info.get("ocsf_classification", {})
        complexity = parser_info.get("parser_complexity", {}).get("level", "Unknown")

        commit_prompt = f"""Generate a professional Git commit message following conventional commit standards for:

Pipeline Deployment:
- Parser: {parser_id}
- Source Type: {source_type}
- Source Path: {parser_info.get('source_path', 'unknown')}
- OCSF Class: {ocsf_class.get('class_name', 'Unknown')} (UID: {ocsf_class.get('class_uid', 0)})
- Complexity: {complexity}
- Status: {deployment_result.get('status', 'deployed')}
- Pipeline ID: {deployment_result.get('pipeline_id', 'unknown')}

Follow this format:
- Type: feat (new pipeline), fix (bug fix), docs (documentation), etc.
- Scope: parser category or name
- Description: clear, concise description (max 72 chars)
- Body: technical details if significant (optional)

Examples:
feat(cisco-duo): add optimized authentication pipeline with OCSF 3002 mapping
fix(okta-logs): resolve field mapping issue for user.account_uid transformation
feat(aws-guardduty): implement high-volume security findings pipeline

Generate a professional commit message. Respond with ONLY the commit message, no additional text."""

        try:
            response = await self.claude.messages.create(
                model=self.config.get("anthropic", {}).get("model"),
                max_tokens=200,
                temperature=0.1,
                messages=[{"role": "user", "content": commit_prompt}]
            )

            commit_message = response.content[0].text.strip()
            logger.debug(f"Generated commit message: {commit_message[:50]}...")
            return commit_message

        except Exception as e:
            logger.warning(f"Failed to generate commit message with Claude: {e}")
            return self._default_commit_message(parser_info)

    def _default_commit_message(self, parser_info: Dict) -> str:
        """Generate default commit message"""
        parser_id = parser_info.get("parser_id", "unknown")
        source_type = parser_info.get("source_type", "unknown")
        ocsf_class = parser_info.get("ocsf_classification", {}).get("class_name", "Unknown")

        return f"""feat({source_type}): add {parser_id} pipeline

Convert SentinelOne {parser_id} parser to Observo.ai pipeline
OCSF Class: {ocsf_class}
Source: Sentinel-One/ai-siem

Generated by Purple-Pipeline-Parser-Eater"""

    async def _upload_files(self, files: List[Dict], commit_message: str, parser_info: Dict) -> Dict:
        """Upload files to GitHub repository"""
        base_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}"
        uploaded_files = []

        for file_info in files:
            try:
                # Encode content to base64
                content_bytes = file_info["content"].encode("utf-8")
                content_base64 = base64.b64encode(content_bytes).decode("utf-8")

                # Check if file exists (to get SHA for update)
                file_path = file_info["path"]
                url = f"{base_url}/contents/{file_path}"

                existing_sha = None
                async with self.session.get(url) as response:
                    if response.status == 200:
                        existing_file = await response.json()
                        existing_sha = existing_file.get("sha")

                # Prepare upload payload
                payload = {
                    "message": commit_message,
                    "content": content_base64,
                    "branch": "main"
                }

                if existing_sha:
                    payload["sha"] = existing_sha

                # Upload file
                async with self.session.put(url, json=payload) as response:
                    if response.status not in [200, 201]:
                        error_text = await response.text()
                        logger.error(f"Failed to upload {file_path}: {error_text}")
                        continue

                    result = await response.json()
                    uploaded_files.append({
                        "path": file_path,
                        "sha": result.get("content", {}).get("sha"),
                        "url": result.get("content", {}).get("html_url")
                    })

                    logger.debug(f"Uploaded: {file_path}")

                # Rate limiting
                await self.rate_limiter.wait()

            except Exception as e:
                logger.error(f"Failed to upload file {file_info['path']}: {e}")
                continue

        return {
            "parser_id": parser_info.get("parser_id"),
            "uploaded_files": uploaded_files,
            "commit_message": commit_message,
            "repository": f"{self.repo_owner}/{self.repo_name}",
            "uploaded_at": datetime.now().isoformat()
        }

    def _mock_upload_response(self, parser_id: str, files: List[Dict], commit_message: str) -> Dict:
        """Generate mock upload response"""
        return {
            "parser_id": parser_id,
            "uploaded_files": [
                {
                    "path": f["path"],
                    "sha": f"mock-sha-{hash(f['path'])}",
                    "url": f"https://github.com/{self.repo_owner}/{self.repo_name}/blob/main/{f['path']}"
                }
                for f in files
            ],
            "commit_message": commit_message,
            "repository": f"{self.repo_owner}/{self.repo_name}",
            "uploaded_at": datetime.now().isoformat(),
            "mock_mode": True
        }

    async def create_repository_index(self, all_pipelines: List[Dict]) -> Dict:
        """Create index/README for the repository"""
        logger.info("[LIST] Creating repository index")

        # Generate index content
        index_content = self._generate_index_content(all_pipelines)

        # Upload index
        try:
            if self.mock_mode:
                logger.info("[MOCK MODE] Would create repository index")
                return {"status": "mock", "file": "README.md"}
            else:
                return await self._upload_index(index_content)
        except Exception as e:
            logger.error(f"Failed to create repository index: {e}")
            return {"status": "error", "error": str(e)}

    def _generate_index_content(self, all_pipelines: List[Dict]) -> str:
        """Generate index/README content"""
        total_pipelines = len(all_pipelines)
        by_source = {}
        by_ocsf_class = {}

        for pipeline in all_pipelines:
            source = pipeline.get("source_type", "unknown")
            ocsf = pipeline.get("ocsf_classification", {}).get("class_name", "Unknown")

            by_source[source] = by_source.get(source, 0) + 1
            by_ocsf_class[ocsf] = by_ocsf_class.get(ocsf, 0) + 1

        content = f"""# Observo.ai Pipelines - SentinelOne Parser Conversions

**Generated by Purple Pipeline Parser Eater**
**Total Pipelines**: {total_pipelines}
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Overview

This repository contains Observo.ai pipeline configurations converted from SentinelOne ai-siem parsers.
Each pipeline includes optimized LUA transformation code, comprehensive documentation, and deployment configuration.

## Statistics

### By Source Type
{self._format_stats_table(by_source)}

### By OCSF Class
{self._format_stats_table(by_ocsf_class)}

## Repository Structure

```
pipelines/
├── community/          # Community-contributed parsers
│   ├── authentication/ # Authentication-related pipelines (OCSF 3002)
│   ├── network/        # Network activity pipelines
│   └── ...
└── sentinelone/       # SentinelOne official parsers
    ├── authentication/
    ├── security_findings/
    └── ...
```

## Pipeline Structure

Each pipeline directory contains:
- `transform.lua` - LUA transformation function
- `README.md` - Comprehensive documentation
- `config.json` - Observo.ai configuration
- `metadata.json` - Parser metadata and conversion info

## Usage

### Deploying a Pipeline

1. Navigate to desired pipeline directory
2. Review the `README.md` for requirements and configuration
3. Deploy using Observo.ai CLI or API:
   ```bash
   observo-cli pipeline deploy --config config.json
   ```

### Testing a Transformation

```bash
observo-cli pipeline test --lua transform.lua --sample sample_event.json
```

## About

**Tool**: Purple Pipeline Parser Eater v1.0.0
**Source**: [Sentinel-One/ai-siem](https://github.com/Sentinel-One/ai-siem)
**Target**: Observo.ai Platform

### Conversion Process

1. **Scan**: Automated scanning of SentinelOne parser repository
2. **Analyze**: Claude AI semantic analysis of parser logic
3. **Generate**: Optimized LUA code generation with performance tuning
4. **Deploy**: Intelligent deployment to Observo.ai with resource optimization
5. **Document**: Comprehensive documentation with troubleshooting guides

## License

Converted pipelines maintain their original licenses from SentinelOne ai-siem repository.

## Support

For issues or questions about these conversions, please refer to individual pipeline documentation.
"""

        return content

    def _format_stats_table(self, stats: Dict) -> str:
        """Format statistics as markdown table"""
        if not stats:
            return "No data"

        lines = ["| Category | Count |", "|----------|-------|"]
        for key, value in sorted(stats.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"| {key} | {value} |")

        return "\n".join(lines)

    async def _upload_index(self, content: str) -> Dict:
        """Upload index/README to repository root"""
        base_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}"
        url = f"{base_url}/contents/README.md"

        content_base64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        # Check for existing README
        existing_sha = None
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    existing = await response.json()
                    existing_sha = existing.get("sha")
        except (aiohttp.ClientError, asyncio.TimeoutError, aiohttp.ServerTimeoutError) as e:
            logger.debug(f"Failed to check existing README (will create new): {e}")
            existing_sha = None

        payload = {
            "message": "docs: update repository index with pipeline statistics",
            "content": content_base64,
            "branch": "main"
        }

        if existing_sha:
            payload["sha"] = existing_sha

        async with self.session.put(url, json=payload) as response:
            if response.status not in [200, 201]:
                error_text = await response.text()
                raise Exception(f"Failed to upload index: {error_text}")

            result = await response.json()
            return {
                "status": "success",
                "file": "README.md",
                "url": result.get("content", {}).get("html_url")
            }

    def get_statistics(self) -> Dict:
        """Get automation statistics"""
        return self.statistics
