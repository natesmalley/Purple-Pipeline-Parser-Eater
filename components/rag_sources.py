"""
RAG External Sources - Web, GitHub, S3 Scraping for Auto-Updating Knowledge Base
Intelligent scraping with versioning, caching, and diff detection

SECURITY: Includes SSRF protection for web scraping
"""
import logging
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime, timedelta
import hashlib
import json
import re
from urllib.parse import urlparse, urljoin
import base64
import ipaddress
import socket

try:
    import boto3
    from botocore.exceptions import ClientError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False
    logging.warning("boto3 not available, S3 scraping disabled")

logger = logging.getLogger(__name__)


class ExternalSourceScraper:
    """
    Scrape documentation from external sources with auto-update support

    Supported sources:
    - Websites (HTML/Markdown)
    - GitHub repositories
    - S3 buckets
    - Git repositories (local/remote)
    """

    def __init__(self, config: Dict, cache_dir: str = "rag_cache"):
        """
        Initialize external source scraper

        Args:
            config: Configuration dictionary
            cache_dir: Directory for caching scraped content
        """
        self.config = config
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        self.session: Optional[aiohttp.ClientSession] = None
        self.statistics = {
            "sources_scraped": 0,
            "documents_fetched": 0,
            "documents_updated": 0,
            "documents_unchanged": 0,
            "errors": []
        }

        # SECURITY: Define allowed URL schemes and ports
        self.allowed_schemes = ["http", "https"]
        self.allowed_ports = [80, 443, 8080, 8443]
        self.blocked_ips = self._get_blocked_ip_ranges()

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def scrape_source(self, source_config: Dict) -> List[Dict[str, Any]]:
        """
        Scrape documentation from configured source

        Args:
            source_config: Source configuration
                {
                    "type": "website|github|s3|git",
                    "url": "source URL",
                    "patterns": ["*.md", "*.html"],
                    "exclude_patterns": ["test/*"],
                    "auth": {"type": "token|basic", "credentials": ...},
                    "update_interval": "24h",
                    "depth": 2  # for website crawling
                }

        Returns:
            List of scraped documents
        """
        source_type = source_config.get("type")
        self.statistics["sources_scraped"] += 1

        if source_type == "website":
            return await self._scrape_website(source_config)
        elif source_type == "github":
            return await self._scrape_github(source_config)
        elif source_type == "s3":
            return await self._scrape_s3(source_config)
        elif source_type == "git":
            return await self._scrape_git(source_config)
        else:
            logger.error(f"Unknown source type: {source_type}")
            return []

    # ========================================================================
    # SECURITY: SSRF Protection
    # ========================================================================

    def _get_blocked_ip_ranges(self) -> List:
        """
        SECURITY: Get list of blocked IP ranges to prevent SSRF attacks

        Returns:
            List of blocked IP network ranges
        """
        blocked_ranges = [
            ipaddress.ip_network("10.0.0.0/8"),          # Private network
            ipaddress.ip_network("172.16.0.0/12"),       # Private network
            ipaddress.ip_network("192.168.0.0/16"),      # Private network
            ipaddress.ip_network("127.0.0.0/8"),         # Loopback
            ipaddress.ip_network("169.254.0.0/16"),      # Link-local (AWS metadata)
            ipaddress.ip_network("::1/128"),             # IPv6 loopback
            ipaddress.ip_network("fe80::/10"),           # IPv6 link-local
            ipaddress.ip_network("fc00::/7"),            # IPv6 unique local
        ]
        return blocked_ranges

    async def _validate_url_safe(self, url: str) -> bool:
        """
        SECURITY: Validate URL is safe from SSRF attacks

        Args:
            url: URL to validate

        Returns:
            True if safe, False if blocked

        Checks:
        - Scheme is http/https only
        - Port is in allowed list
        - IP is not private/internal
        - Hostname resolves to safe IP
        """
        try:
            parsed = urlparse(url)

            # Check scheme
            if parsed.scheme not in self.allowed_schemes:
                logger.warning(f"SSRF BLOCKED: Invalid scheme {parsed.scheme} for URL: {url}")
                return False

            # Check port
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if port not in self.allowed_ports:
                logger.warning(f"SSRF BLOCKED: Invalid port {port} for URL: {url}")
                return False

            # Resolve hostname to IP
            hostname = parsed.hostname
            if not hostname:
                logger.warning(f"SSRF BLOCKED: No hostname in URL: {url}")
                return False

            # Check if hostname is an IP address
            try:
                ip_obj = ipaddress.ip_address(hostname)
                # Direct IP access - check against blocked ranges
                for blocked_range in self.blocked_ips:
                    if ip_obj in blocked_range:
                        logger.warning(f"SSRF BLOCKED: IP {ip_obj} is in blocked range for URL: {url}")
                        return False
            except ValueError:
                # Hostname is domain name - resolve it
                try:
                    loop = asyncio.get_event_loop()
                    addr_info = await loop.getaddrinfo(hostname, port, family=socket.AF_INET)

                    for info in addr_info:
                        ip_str = info[4][0]
                        ip_obj = ipaddress.ip_address(ip_str)

                        # Check if resolved IP is in blocked ranges
                        for blocked_range in self.blocked_ips:
                            if ip_obj in blocked_range:
                                logger.warning(f"SSRF BLOCKED: Hostname {hostname} resolves to blocked IP {ip_obj}")
                                return False

                except socket.gaierror as e:
                    logger.error(f"Failed to resolve hostname {hostname}: {e}")
                    return False

            # URL is safe
            return True

        except Exception as e:
            logger.error(f"Error validating URL {url}: {e}")
            return False

    # ========================================================================
    # Website Scraping
    # ========================================================================

    async def _scrape_website(self, config: Dict) -> List[Dict[str, Any]]:
        """
        Scrape documentation from website

        Args:
            config: Website configuration

        Returns:
            List of scraped pages
        """
        base_url = config.get("url")
        max_depth = config.get("depth", 2)
        patterns = config.get("patterns", ["*.md", "*.html"])

        logger.info(f"Scraping website: {base_url} (depth: {max_depth})")

        # Check if cached version is fresh
        if self._is_cache_fresh(base_url, config.get("update_interval", "24h")):
            logger.info(f"Using cached version of {base_url}")
            return self._load_from_cache(base_url)

        documents = []
        visited = set()
        to_visit = [(base_url, 0)]  # (url, depth)

        while to_visit:
            url, depth = to_visit.pop(0)

            if url in visited or depth > max_depth:
                continue

            visited.add(url)

            # SECURITY FIX: Validate URL before fetching
            if not await self._validate_url_safe(url):
                logger.warning(f"Skipping unsafe URL: {url}")
                continue

            try:
                # Fetch page
                async with self.session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch {url}: {response.status}")
                        continue

                    content_type = response.headers.get("Content-Type", "")
                    content = await response.text()

                    # Extract documentation
                    doc = await self._extract_web_content(url, content, content_type)
                    if doc:
                        documents.append(doc)
                        self.statistics["documents_fetched"] += 1

                    # Find links for further crawling
                    if depth < max_depth:
                        links = self._extract_links(content, base_url, url)
                        for link in links:
                            if self._matches_patterns(link, patterns):
                                to_visit.append((link, depth + 1))

            except Exception as e:
                error_msg = f"Error scraping {url}: {e}"
                logger.error(error_msg)
                self.statistics["errors"].append(error_msg)

        # Save to cache
        self._save_to_cache(base_url, documents)

        logger.info(f"[OK] Scraped {len(documents)} documents from {base_url}")
        return documents

    async def _extract_web_content(
        self,
        url: str,
        content: str,
        content_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Extract usable content from web page

        Args:
            url: Page URL
            content: Page content
            content_type: Content MIME type

        Returns:
            Extracted document or None
        """
        # Handle Markdown
        if "markdown" in content_type or url.endswith(".md"):
            return {
                "url": url,
                "title": self._extract_title_from_markdown(content),
                "content": content,
                "content_type": "markdown",
                "fetched_at": datetime.now().isoformat(),
                "source_type": "website"
            }

        # Handle HTML
        elif "html" in content_type:
            # Extract main content (simple heuristic)
            # In production, use BeautifulSoup for better parsing
            text_content = self._extract_text_from_html(content)
            if text_content:
                return {
                    "url": url,
                    "title": self._extract_title_from_html(content),
                    "content": text_content,
                    "content_type": "html",
                    "fetched_at": datetime.now().isoformat(),
                    "source_type": "website"
                }

        return None

    def _extract_title_from_markdown(self, content: str) -> str:
        """Extract title from markdown (first # header)"""
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        return match.group(1) if match else "Untitled"

    def _extract_title_from_html(self, content: str) -> str:
        """Extract title from HTML <title> tag"""
        match = re.search(r"<title>(.+?)</title>", content, re.IGNORECASE)
        return match.group(1) if match else "Untitled"

    def _extract_text_from_html(self, html: str) -> str:
        """Simple HTML to text extraction"""
        # Remove scripts and styles
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", text)

        # Clean up whitespace
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def _extract_links(self, html: str, base_url: str, current_url: str) -> List[str]:
        """Extract absolute links from HTML"""
        # Simple regex-based link extraction
        # In production, use BeautifulSoup
        links = re.findall(r'href=["\']([^"\']+)["\']', html)

        absolute_links = []
        for link in links:
            absolute_link = urljoin(current_url, link)
            # Only follow links from same domain
            if urlparse(absolute_link).netloc == urlparse(base_url).netloc:
                absolute_links.append(absolute_link)

        return absolute_links

    # ========================================================================
    # GitHub Scraping
    # ========================================================================

    async def _scrape_github(self, config: Dict) -> List[Dict[str, Any]]:
        """
        Scrape documentation from GitHub repository

        Args:
            config: GitHub configuration
                {
                    "url": "https://github.com/owner/repo",
                    "branch": "main",
                    "paths": ["docs/", "README.md"],
                    "patterns": ["*.md"],
                    "auth": {"token": "ghp_..."}
                }

        Returns:
            List of scraped documents
        """
        repo_url = config.get("url")
        branch = config.get("branch", "main")
        paths = config.get("paths", [""])
        patterns = config.get("patterns", ["*.md"])
        auth_token = config.get("auth", {}).get("token")

        logger.info(f"Scraping GitHub: {repo_url} (branch: {branch})")

        # Parse GitHub URL
        match = re.match(r"https://github\.com/([^/]+)/([^/]+)", repo_url)
        if not match:
            logger.error(f"Invalid GitHub URL: {repo_url}")
            return []

        owner, repo = match.groups()

        # Check cache
        cache_key = f"github:{owner}/{repo}:{branch}"
        if self._is_cache_fresh(cache_key, config.get("update_interval", "24h")):
            logger.info(f"Using cached version of {repo_url}")
            return self._load_from_cache(cache_key)

        documents = []

        # Fetch repository contents via GitHub API
        headers = {"Accept": "application/vnd.github+json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        for path in paths:
            try:
                api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"

                async with self.session.get(api_url, headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch {api_url}: {response.status}")
                        continue

                    contents = await response.json()

                    # Handle single file vs directory
                    if isinstance(contents, dict):
                        contents = [contents]

                    for item in contents:
                        if item["type"] == "file":
                            if self._matches_patterns(item["name"], patterns):
                                doc = await self._fetch_github_file(item, owner, repo, headers)
                                if doc:
                                    documents.append(doc)
                                    self.statistics["documents_fetched"] += 1

                        elif item["type"] == "dir":
                            # Recursively fetch directory contents
                            sub_config = config.copy()
                            sub_config["paths"] = [item["path"]]
                            sub_docs = await self._scrape_github(sub_config)
                            documents.extend(sub_docs)

            except Exception as e:
                error_msg = f"Error scraping GitHub path {path}: {e}"
                logger.error(error_msg)
                self.statistics["errors"].append(error_msg)

        # Save to cache
        self._save_to_cache(cache_key, documents)

        logger.info(f"[OK] Scraped {len(documents)} documents from {repo_url}")
        return documents

    async def _fetch_github_file(
        self,
        file_info: Dict,
        owner: str,
        repo: str,
        headers: Dict
    ) -> Optional[Dict[str, Any]]:
        """Fetch individual file from GitHub"""
        try:
            # File content is base64 encoded in GitHub API response
            if "content" in file_info:
                content = base64.b64decode(file_info["content"]).decode("utf-8")
            else:
                # Fetch file content separately
                async with self.session.get(file_info["download_url"], headers=headers) as response:
                    if response.status != 200:
                        return None
                    content = await response.text()

            return {
                "url": file_info["html_url"],
                "title": file_info["name"],
                "content": content,
                "content_type": "markdown" if file_info["name"].endswith(".md") else "text",
                "path": file_info["path"],
                "sha": file_info["sha"],  # For version tracking
                "fetched_at": datetime.now().isoformat(),
                "source_type": "github",
                "repository": f"{owner}/{repo}"
            }

        except Exception as e:
            logger.error(f"Failed to fetch GitHub file {file_info['path']}: {e}")
            return None

    # ========================================================================
    # S3 Scraping
    # ========================================================================

    async def _scrape_s3(self, config: Dict) -> List[Dict[str, Any]]:
        """
        Scrape documentation from S3 bucket

        Args:
            config: S3 configuration
                {
                    "bucket": "my-docs-bucket",
                    "prefix": "observo-docs/",
                    "patterns": ["*.md", "*.txt"],
                    "auth": {
                        "aws_access_key_id": "...",
                        "aws_secret_access_key": "...",
                        "region": "us-east-1"
                    }
                }

        Returns:
            List of scraped documents
        """
        if not S3_AVAILABLE:
            logger.error("boto3 not available, cannot scrape S3")
            return []

        bucket = config.get("bucket")
        prefix = config.get("prefix", "")
        patterns = config.get("patterns", ["*.md", "*.txt"])
        auth = config.get("auth", {})

        logger.info(f"Scraping S3: s3://{bucket}/{prefix}")

        # Check cache
        cache_key = f"s3:{bucket}:{prefix}"
        if self._is_cache_fresh(cache_key, config.get("update_interval", "24h")):
            logger.info(f"Using cached version of s3://{bucket}/{prefix}")
            return self._load_from_cache(cache_key)

        documents = []

        try:
            # Initialize S3 client
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=auth.get("aws_access_key_id"),
                aws_secret_access_key=auth.get("aws_secret_access_key"),
                region_name=auth.get("region", "us-east-1")
            )

            # List objects
            paginator = s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

            for page in pages:
                for obj in page.get("Contents", []):
                    key = obj["Key"]

                    # Check if matches patterns
                    if self._matches_patterns(key, patterns):
                        try:
                            # Fetch object
                            response = s3_client.get_object(Bucket=bucket, Key=key)
                            content = response["Body"].read().decode("utf-8")

                            doc = {
                                "url": f"s3://{bucket}/{key}",
                                "title": Path(key).name,
                                "content": content,
                                "content_type": self._detect_content_type(key),
                                "path": key,
                                "size": obj["Size"],
                                "last_modified": obj["LastModified"].isoformat(),
                                "etag": obj["ETag"],  # For version tracking
                                "fetched_at": datetime.now().isoformat(),
                                "source_type": "s3",
                                "bucket": bucket
                            }

                            documents.append(doc)
                            self.statistics["documents_fetched"] += 1

                        except Exception as e:
                            error_msg = f"Failed to fetch s3://{bucket}/{key}: {e}"
                            logger.error(error_msg)
                            self.statistics["errors"].append(error_msg)

        except ClientError as e:
            error_msg = f"S3 scraping failed: {e}"
            logger.error(error_msg)
            self.statistics["errors"].append(error_msg)

        # Save to cache
        self._save_to_cache(cache_key, documents)

        logger.info(f"[OK] Scraped {len(documents)} documents from s3://{bucket}/{prefix}")
        return documents

    # ========================================================================
    # Git Repository Scraping
    # ========================================================================

    async def _scrape_git(self, config: Dict) -> List[Dict[str, Any]]:
        """
        Scrape documentation from Git repository (local or remote)

        Args:
            config: Git configuration

        Returns:
            List of scraped documents
        """
        # For local git repos, just scan the filesystem
        # For remote repos, use GitHub/GitLab API or git clone

        repo_path = config.get("path")
        patterns = config.get("patterns", ["*.md"])

        logger.info(f"Scraping Git repository: {repo_path}")

        documents = []
        repo_path = Path(repo_path)

        if not repo_path.exists():
            logger.error(f"Git repository not found: {repo_path}")
            return []

        # Find matching files
        for pattern in patterns:
            for file_path in repo_path.rglob(pattern):
                if file_path.is_file():
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        doc = {
                            "url": f"file://{file_path}",
                            "title": file_path.name,
                            "content": content,
                            "content_type": "markdown" if file_path.suffix == ".md" else "text",
                            "path": str(file_path.relative_to(repo_path)),
                            "fetched_at": datetime.now().isoformat(),
                            "source_type": "git",
                            "repository": str(repo_path)
                        }
                        documents.append(doc)
                        self.statistics["documents_fetched"] += 1

                    except Exception as e:
                        error_msg = f"Failed to read {file_path}: {e}"
                        logger.error(error_msg)
                        self.statistics["errors"].append(error_msg)

        logger.info(f"[OK] Scraped {len(documents)} documents from {repo_path}")
        return documents

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _matches_patterns(self, path: str, patterns: List[str]) -> bool:
        """Check if path matches any pattern"""
        from fnmatch import fnmatch
        return any(fnmatch(path, pattern) for pattern in patterns)

    def _detect_content_type(self, filename: str) -> str:
        """Detect content type from filename"""
        ext = Path(filename).suffix.lower()
        if ext == ".md":
            return "markdown"
        elif ext in [".html", ".htm"]:
            return "html"
        elif ext == ".json":
            return "json"
        else:
            return "text"

    def _is_cache_fresh(self, cache_key: str, interval: str) -> bool:
        """Check if cached version is still fresh"""
        # SECURITY: MD5 used for cache filename only, not cryptographic security
        cache_file = self.cache_dir / f"{hashlib.md5(cache_key.encode(), usedforsecurity=False).hexdigest()}.json"

        if not cache_file.exists():
            return False

        # Parse interval (e.g., "24h", "7d", "1w")
        interval_seconds = self._parse_interval(interval)

        # Check cache age
        cache_age = datetime.now().timestamp() - cache_file.stat().st_mtime
        return cache_age < interval_seconds

    def _parse_interval(self, interval: str) -> int:
        """Parse interval string to seconds"""
        if interval.endswith("h"):
            return int(interval[:-1]) * 3600
        elif interval.endswith("d"):
            return int(interval[:-1]) * 86400
        elif interval.endswith("w"):
            return int(interval[:-1]) * 604800
        else:
            return 86400  # Default: 24 hours

    def _load_from_cache(self, cache_key: str) -> List[Dict[str, Any]]:
        """Load documents from cache"""
        # SECURITY: MD5 used for cache filename only, not cryptographic security
        cache_file = self.cache_dir / f"{hashlib.md5(cache_key.encode(), usedforsecurity=False).hexdigest()}.json"

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.statistics["documents_fetched"] += len(data)
                return data
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
            return []

    def _save_to_cache(self, cache_key: str, documents: List[Dict[str, Any]]):
        """Save documents to cache"""
        # SECURITY: MD5 used for cache filename only, not cryptographic security
        cache_file = self.cache_dir / f"{hashlib.md5(cache_key.encode(), usedforsecurity=False).hexdigest()}.json"

        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(documents, f, indent=2)
            logger.debug(f"Saved {len(documents)} documents to cache")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get scraping statistics"""
        return self.statistics


class AutoUpdateManager:
    """
    Manage automatic updates of RAG knowledge base from external sources
    """

    def __init__(self, rag_knowledge_base, scraper: ExternalSourceScraper):
        """
        Initialize auto-update manager

        Args:
            rag_knowledge_base: RAG knowledge base instance
            scraper: External source scraper
        """
        self.rag = rag_knowledge_base
        self.scraper = scraper
        self.update_log: List[Dict[str, Any]] = []

    async def update_from_sources(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Update RAG knowledge base from all configured sources

        Args:
            sources: List of source configurations

        Returns:
            Update statistics
        """
        logger.info(f"Starting auto-update from {len(sources)} sources")

        total_updated = 0
        total_added = 0
        total_unchanged = 0

        for source in sources:
            try:
                # Scrape source
                documents = await self.scraper.scrape_source(source)

                # Update RAG
                for doc in documents:
                    # Check if document exists and has changed
                    doc_hash = self._compute_doc_hash(doc["content"])
                    existing_hash = self._get_existing_doc_hash(doc.get("url", doc.get("path")))

                    if existing_hash is None:
                        # New document
                        await self._add_to_rag(doc)
                        total_added += 1
                    elif existing_hash != doc_hash:
                        # Document changed
                        await self._update_in_rag(doc)
                        total_updated += 1
                    else:
                        # Document unchanged
                        total_unchanged += 1

                self.update_log.append({
                    "source": source.get("url", source.get("bucket")),
                    "type": source.get("type"),
                    "documents": len(documents),
                    "timestamp": datetime.now().isoformat(),
                    "status": "success"
                })

            except Exception as e:
                error_msg = f"Failed to update from source {source}: {e}"
                logger.error(error_msg)
                self.update_log.append({
                    "source": source.get("url", source.get("bucket")),
                    "type": source.get("type"),
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                    "status": "failed"
                })

        return {
            "total_added": total_added,
            "total_updated": total_updated,
            "total_unchanged": total_unchanged,
            "sources_processed": len(sources),
            "timestamp": datetime.now().isoformat()
        }

    def _compute_doc_hash(self, content: str) -> str:
        """Compute hash of document content"""
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_existing_doc_hash(self, identifier: str) -> Optional[str]:
        """Get hash of existing document (if any)"""
        # This would query the RAG knowledge base
        # For now, return None (always treat as new)
        return None

    async def _add_to_rag(self, doc: Dict[str, Any]):
        """Add new document to RAG"""
        if self.rag and self.rag.enabled:
            self.rag.add_document(
                content=doc["content"],
                title=doc.get("title", "Untitled"),
                source=doc.get("url", doc.get("path")),
                doc_type=doc.get("source_type", "external"),
                metadata=doc
            )

    async def _update_in_rag(self, doc: Dict[str, Any]):
        """Update existing document in RAG"""
        # Would need to delete old version and add new
        # For now, just add (Milvus will handle duplicates based on embedding similarity)
        await self._add_to_rag(doc)

    def get_update_log(self) -> List[Dict[str, Any]]:
        """Get update history"""
        return self.update_log
