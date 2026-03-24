"""AI-SIEM parser-to-pipeline source component converter.

Fetches parser records from Sentinel-One/ai-siem/parsers, learns source component
patterns from /pipelines/community templates, classifies parser ingestion style,
and emits pipeline-style source JSON components.
"""

from __future__ import annotations

import asyncio
import copy
import io
import logging
import re
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional, Sequence, Tuple

import aiohttp
import yaml

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com/repos/Sentinel-One/ai-siem"
GITHUB_ARCHIVE_URL = "https://codeload.github.com/Sentinel-One/ai-siem/zip/refs/heads/main"


@dataclass
class PipelineTemplate:
    """Pipeline template with extracted source component."""

    name: str
    source: Dict[str, Any]
    source_configs: List[Dict[str, Any]]
    transforms: List[Dict[str, Any]]
    destinations: List[Dict[str, Any]]


@dataclass
class ParserRecord:
    """Parser record from ai-siem repo."""

    name: str
    path: str
    config_file: Optional[str]
    config_text: str
    metadata: Dict[str, Any]


def normalize_name(name: str) -> str:
    """Normalize parser/pipeline names for matching."""
    lowered = name.lower().strip()
    lowered = lowered.replace("-latest", "")
    lowered = lowered.replace("_latest", "")
    lowered = lowered.replace("-lastest", "")
    lowered = lowered.replace("_lastest", "")
    lowered = re.sub(r"[^a-z0-9]+", "_", lowered)
    return re.sub(r"_+", "_", lowered).strip("_")


def tokenize(name: str) -> List[str]:
    """Tokenize normalized names."""
    return [tok for tok in normalize_name(name).split("_") if tok]


def token_overlap_score(left: str, right: str) -> float:
    """Compute simple token overlap score."""
    lset = set(tokenize(left))
    rset = set(tokenize(right))
    if not lset or not rset:
        return 0.0
    overlap = len(lset.intersection(rset))
    return overlap / max(len(lset), len(rset))


class AISIEMPipelineConverter:
    """Convert parser records into pipeline-style source components."""

    SYSLOG_KEYWORDS = {
        "syslog",
        "asa",
        "firewall",
        "fortigate",
        "fortinet",
        "meraki",
        "ios",
        "router",
        "switch",
        "cef",
        "netscaler",
        "pan",
        "palo",
    }

    PUSH_KEYWORDS = {
        "collector",
        "cloudtrail",
        "s3",
        "okta",
        "duo",
        "proofpoint",
        "api",
        "webhook",
        "audit",
        "workspace",
        "guardduty",
        "waf",
        "cdn",
        "dns",
    }

    def __init__(
        self,
        github_token: Optional[str] = None,
        api_base: str = GITHUB_API_BASE,
        timeout_seconds: int = 60,
    ):
        self.api_base = api_base.rstrip("/")
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Purple-Pipeline-Parser-Eater/1.0",
        }
        if github_token and github_token not in {"dry-run-mode", "your-github-token-here"}:
            self.headers["Authorization"] = f"token {github_token}"

        self._timeout_seconds = timeout_seconds
        self._session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)
            self._session = aiohttp.ClientSession(headers=self.headers, timeout=timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _fetch_json(self, url: str) -> Any:
        session = await self._ensure_session()
        async with session.get(url) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"GitHub API error {resp.status} for {url}: {text[:200]}")
            return await resp.json()

    async def _fetch_text(self, url: str) -> str:
        session = await self._ensure_session()
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"File fetch error {resp.status} for {url}")
            return await resp.text()

    async def _fetch_bytes(self, url: str) -> bytes:
        last_error: Optional[Exception] = None
        for _ in range(3):
            try:
                session = await self._ensure_session()
                async with session.get(url) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise RuntimeError(f"File fetch error {resp.status} for {url}: {text[:200]}")
                    return await resp.read()
            except asyncio.TimeoutError as exc:
                last_error = exc
                logger.warning("Timeout fetching %s, retrying...", url)
                continue
        if last_error:
            raise last_error
        raise RuntimeError(f"Failed to fetch bytes from {url}")

    async def _list_dirs(self, path: str) -> List[Dict[str, Any]]:
        payload = await self._fetch_json(f"{self.api_base}/contents/{path}?ref=main")
        return [item for item in payload if item.get("type") == "dir"]

    async def _list_dir_contents(self, path: str) -> List[Dict[str, Any]]:
        payload = await self._fetch_json(f"{self.api_base}/contents/{path}?ref=main")
        return payload if isinstance(payload, list) else []

    async def load_pipeline_templates(self) -> List[PipelineTemplate]:
        """Load all pipeline templates from pipelines/community."""
        template_dirs = await self._list_dirs("pipelines/community")
        templates: List[PipelineTemplate] = []

        for item in template_dirs:
            folder = item["name"]
            contents = await self._list_dir_contents(item["path"])
            json_file = next(
                (x for x in contents if x.get("type") == "file" and x.get("name", "").startswith("observo_export_pipeline_") and x["name"].endswith(".json")),
                None,
            )
            if not json_file:
                continue
            try:
                raw = await self._fetch_text(json_file["download_url"])
                parsed = yaml.safe_load(raw)
            except Exception as exc:
                logger.warning("Skipping template %s: %s", folder, exc)
                continue

            source = parsed.get("source") if isinstance(parsed, dict) else None
            if not isinstance(source, dict):
                continue
            source_configs = source.get("sourceConfigs", [])
            transforms = parsed.get("transforms", [])
            destinations = parsed.get("destinations", [])
            templates.append(
                PipelineTemplate(
                    name=folder,
                    source=source,
                    source_configs=source_configs if isinstance(source_configs, list) else [],
                    transforms=transforms if isinstance(transforms, list) else [],
                    destinations=destinations if isinstance(destinations, list) else [],
                )
            )

        return templates

    async def _load_pipeline_templates_from_archive(self) -> List[PipelineTemplate]:
        archive = await self._fetch_bytes(GITHUB_ARCHIVE_URL)
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            names = zf.namelist()
            root = next((n.split("/", 1)[0] for n in names if n.endswith("/")), names[0].split("/", 1)[0])
            template_prefix = f"{root}/pipelines/community/"

            pipeline_dirs: Dict[str, str] = {}
            for name in names:
                if not name.startswith(template_prefix):
                    continue
                rel = name[len(template_prefix):]
                parts = PurePosixPath(rel).parts
                if len(parts) >= 2:
                    pipeline_dirs[parts[0]] = f"{template_prefix}{parts[0]}/"

            templates: List[PipelineTemplate] = []
            for folder in sorted(pipeline_dirs.keys()):
                folder_prefix = pipeline_dirs[folder]
                json_path = next(
                    (
                        n for n in names
                        if n.startswith(folder_prefix)
                        and n.endswith(".json")
                        and PurePosixPath(n).name.startswith("observo_export_pipeline_")
                    ),
                    None,
                )
                if not json_path:
                    continue
                try:
                    parsed = yaml.safe_load(zf.read(json_path).decode("utf-8"))
                except Exception as exc:
                    logger.warning("Skipping template %s from archive: %s", folder, exc)
                    continue

                source = parsed.get("source") if isinstance(parsed, dict) else None
                if isinstance(source, dict):
                    source_configs = source.get("sourceConfigs", [])
                    transforms = parsed.get("transforms", [])
                    destinations = parsed.get("destinations", [])
                    templates.append(
                        PipelineTemplate(
                            name=folder,
                            source=source,
                            source_configs=source_configs if isinstance(source_configs, list) else [],
                            transforms=transforms if isinstance(transforms, list) else [],
                            destinations=destinations if isinstance(destinations, list) else [],
                        )
                    )

            return templates

    async def load_parser_records(self) -> List[ParserRecord]:
        """Load parser records from parsers/community."""
        parser_dirs = await self._list_dirs("parsers/community")
        parsers: List[ParserRecord] = []

        for parser_dir in parser_dirs:
            parser_name = parser_dir["name"]
            contents = await self._list_dir_contents(parser_dir["path"])
            metadata_file = next((x for x in contents if x.get("name") == "metadata.yaml"), None)
            config_file = next(
                (
                    x
                    for x in contents
                    if x.get("type") == "file"
                    and (x.get("name", "").endswith(".conf") or x.get("name", "").endswith(".json") or x.get("name", "").endswith(".yaml"))
                    and x.get("name") != "metadata.yaml"
                ),
                None,
            )

            metadata: Dict[str, Any] = {}
            if metadata_file:
                try:
                    metadata_text = await self._fetch_text(metadata_file["download_url"])
                    loaded = yaml.safe_load(metadata_text)
                    metadata = loaded if isinstance(loaded, dict) else {}
                except Exception as exc:
                    logger.warning("Failed metadata parse for %s: %s", parser_name, exc)

            config_text = ""
            if config_file:
                try:
                    config_text = await self._fetch_text(config_file["download_url"])
                except Exception as exc:
                    logger.warning("Failed config fetch for %s: %s", parser_name, exc)

            parsers.append(
                ParserRecord(
                    name=parser_name,
                    path=parser_dir["path"],
                    config_file=config_file["name"] if config_file else None,
                    config_text=config_text,
                    metadata=metadata,
                )
            )

        return parsers

    async def _load_parser_records_from_archive(self) -> List[ParserRecord]:
        archive = await self._fetch_bytes(GITHUB_ARCHIVE_URL)
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            names = zf.namelist()
            root = next((n.split("/", 1)[0] for n in names if n.endswith("/")), names[0].split("/", 1)[0])
            parser_prefix = f"{root}/parsers/community/"

            parser_dirs: Dict[str, str] = {}
            for name in names:
                if not name.startswith(parser_prefix):
                    continue
                rel = name[len(parser_prefix):]
                parts = PurePosixPath(rel).parts
                if len(parts) >= 2:
                    parser_dirs[parts[0]] = f"{parser_prefix}{parts[0]}/"

            parsers: List[ParserRecord] = []
            for parser_name in sorted(parser_dirs.keys()):
                folder_prefix = parser_dirs[parser_name]
                metadata_path = next(
                    (n for n in names if n.startswith(folder_prefix) and PurePosixPath(n).name == "metadata.yaml"),
                    None,
                )
                config_path = next(
                    (
                        n for n in names
                        if n.startswith(folder_prefix)
                        and (
                            n.endswith(".conf")
                            or n.endswith(".json")
                            or n.endswith(".yaml")
                        )
                        and PurePosixPath(n).name != "metadata.yaml"
                    ),
                    None,
                )

                metadata: Dict[str, Any] = {}
                if metadata_path:
                    try:
                        loaded = yaml.safe_load(zf.read(metadata_path).decode("utf-8"))
                        metadata = loaded if isinstance(loaded, dict) else {}
                    except Exception as exc:
                        logger.warning("Failed metadata parse for %s from archive: %s", parser_name, exc)

                config_text = ""
                config_file = None
                if config_path:
                    config_file = PurePosixPath(config_path).name
                    try:
                        config_text = zf.read(config_path).decode("utf-8", errors="replace")
                    except Exception as exc:
                        logger.warning("Failed config read for %s from archive: %s", parser_name, exc)

                parsers.append(
                    ParserRecord(
                        name=parser_name,
                        path=f"parsers/community/{parser_name}",
                        config_file=config_file,
                        config_text=config_text,
                        metadata=metadata,
                    )
                )

            return parsers

    @staticmethod
    def _is_push_from_source(source: Dict[str, Any]) -> bool:
        source_type = str(source.get("type", "")).upper()
        if source.get("pushBased") is True:
            return True
        return source_type in {"SCOL", "SCOL_OKTA", "AWS_S3", "HTTP", "KAFKA"}

    @staticmethod
    def _sanitize_component(component: Dict[str, Any]) -> Dict[str, Any]:
        keep_keys = {
            "templateId",
            "templateVersion",
            "templateName",
            "category",
            "processorType",
            "type",
            "position",
            "config",
            "name",
            "description",
        }
        return {k: copy.deepcopy(v) for k, v in component.items() if k in keep_keys}

    def _extract_processing_profile(self, template: PipelineTemplate) -> Dict[str, Any]:
        parsing_components = [
            self._sanitize_component(cfg)
            for cfg in template.source_configs
            if isinstance(cfg, dict)
        ]

        serialization_transforms = []
        for tr in template.transforms:
            if not isinstance(tr, dict):
                continue
            tname = str(tr.get("templateName", "")).lower()
            cfg = tr.get("config", {})
            serialized = self._sanitize_component(tr)
            has_serializer_key = False
            if isinstance(cfg, dict):
                groups = cfg.get("config_groups")
                if isinstance(groups, list):
                    for group in groups:
                        if isinstance(group, dict) and "serializer" in group:
                            has_serializer_key = True
                            break
            if "serializer" in tname or "ocsfserializer" in tname or has_serializer_key:
                serialization_transforms.append(serialized)

        destination_components = [
            self._sanitize_component(dst)
            for dst in template.destinations
            if isinstance(dst, dict)
        ]

        has_parsing = len(parsing_components) > 0
        has_serializer = len(serialization_transforms) > 0
        has_destination = len(destination_components) > 0

        return {
            "parsing_components": parsing_components,
            "serialization_components": serialization_transforms,
            "destination_components": destination_components,
            "validation": {
                "has_parsing_components": has_parsing,
                "has_serialization_component": has_serializer,
                "has_destination_component": has_destination,
                "buildable": has_parsing and has_serializer and has_destination,
            },
        }

    def _match_pipeline_template(
        self,
        parser_name: str,
        templates: Sequence[PipelineTemplate],
    ) -> Tuple[Optional[PipelineTemplate], float]:
        parser_norm = normalize_name(parser_name)

        for tpl in templates:
            if parser_norm == normalize_name(tpl.name):
                return tpl, 1.0

        best: Optional[PipelineTemplate] = None
        best_score = 0.0
        for tpl in templates:
            score = token_overlap_score(parser_name, tpl.name)
            if score > best_score:
                best = tpl
                best_score = score

        if best_score >= 0.5:
            return best, best_score
        return None, 0.0

    def _classify_parser(
        self,
        parser: ParserRecord,
        matched_template: Optional[PipelineTemplate],
    ) -> Tuple[str, List[str]]:
        parser_norm = normalize_name(parser.name)
        reasons: List[str] = []

        if matched_template:
            if self._is_push_from_source(matched_template.source):
                reasons.append("matched_pipeline_source_is_push")
                return "push", reasons
            src_type = str(matched_template.source.get("type", "")).upper()
            if src_type == "SYSLOG":
                reasons.append("matched_pipeline_source_type_syslog")
                return "syslog", reasons

        metadata_yaml = yaml.safe_dump(parser.metadata).lower() if parser.metadata else ""
        conf_text = (parser.config_text or "").lower()

        if any(k in parser_norm for k in self.SYSLOG_KEYWORDS):
            reasons.append("parser_name_syslog_keyword")
        if "syslog" in metadata_yaml or "syslog" in conf_text or "cef" in conf_text:
            reasons.append("parser_content_syslog_signal")
        if reasons:
            return "syslog", reasons

        push_reasons: List[str] = []
        if any(k in parser_norm for k in self.PUSH_KEYWORDS):
            push_reasons.append("parser_name_push_keyword")
        if "ingestion_method: streaming" in metadata_yaml:
            push_reasons.append("metadata_streaming")
        if any(k in conf_text for k in ["http", "https", "api", "poll", "collector"]):
            push_reasons.append("parser_content_push_signal")
        if push_reasons:
            return "push", push_reasons

        return "other", []

    @staticmethod
    def _build_fallback_source(mode: str, parser_name: str) -> Dict[str, Any]:
        if mode == "syslog":
            return {
                "templateName": "SYSLOG",
                "name": f"{normalize_name(parser_name)}_syslog_source",
                "description": f"Autogenerated syslog source for {parser_name}",
                "type": "SYSLOG",
                "logFormat": "SYSLOG",
                "pushBased": False,
                "config": {},
            }

        return {
            "templateName": "SCOL",
            "name": f"{normalize_name(parser_name)}_push_source",
            "description": f"Autogenerated push source for {parser_name}",
            "type": "SCOL",
            "logFormat": "LOG_FORMAT_UNSPECIFIED",
            "pushBased": True,
            "config": {},
        }

    def _convert_single(
        self,
        parser: ParserRecord,
        templates: Sequence[PipelineTemplate],
        default_push_template: Optional[PipelineTemplate] = None,
    ) -> Optional[Dict[str, Any]]:
        matched_template, match_score = self._match_pipeline_template(parser.name, templates)
        mode, reasons = self._classify_parser(parser, matched_template)
        if mode not in {"syslog", "push"}:
            return None

        if matched_template:
            source_component = copy.deepcopy(matched_template.source)
        else:
            source_component = self._build_fallback_source(mode, parser.name)

        source_component["name"] = f"source-{normalize_name(parser.name)}"
        source_component["description"] = f"Generated from parser {parser.name} ({mode})"

        processing_profile = None
        processing_template = matched_template
        if mode == "push" and processing_template is None:
            processing_template = default_push_template
        if mode == "push" and processing_template is not None:
            processing_profile = self._extract_processing_profile(processing_template)

        return {
            "parser_name": parser.name,
            "parser_path": parser.path,
            "config_file": parser.config_file,
            "ingestion_mode": mode,
            "classification_reasons": reasons,
            "matched_pipeline_template": matched_template.name if matched_template else None,
            "template_match_score": round(match_score, 3),
            "source": source_component,
            "processing_template_used": processing_template.name if processing_template else None,
            "processing_profile": processing_profile,
        }

    async def convert(self, max_parsers: Optional[int] = None) -> Dict[str, Any]:
        """Run end-to-end conversion and return result payload."""
        used_archive_fallback = False
        try:
            templates = await self.load_pipeline_templates()
            parsers = await self.load_parser_records()
        except Exception as exc:
            err = str(exc)
            should_fallback = False
            if isinstance(exc, RuntimeError) and ("GitHub API error 401" in err or "GitHub API error 403" in err):
                should_fallback = True
            if isinstance(exc, asyncio.TimeoutError):
                should_fallback = True
            if "Cannot connect to host" in err or "nodename nor servname provided" in err:
                should_fallback = True

            if not should_fallback:
                raise

            logger.warning("GitHub API unavailable/rate-limited, falling back to archive download")
            templates = await self._load_pipeline_templates_from_archive()
            parsers = await self._load_parser_records_from_archive()
            used_archive_fallback = True

        if max_parsers is not None:
            parsers = parsers[:max_parsers]

        push_templates = [t for t in templates if self._is_push_from_source(t.source)]
        default_push_template = push_templates[0] if push_templates else None

        converted: List[Dict[str, Any]] = []
        for parser in parsers:
            converted_entry = self._convert_single(parser, templates, default_push_template)
            if converted_entry:
                converted.append(converted_entry)

        push_entries = [x for x in converted if x["ingestion_mode"] == "push"]
        push_buildable = 0
        push_buildable_matched = 0
        push_buildable_fallback = 0
        for entry in push_entries:
            profile = entry.get("processing_profile") or {}
            validation = profile.get("validation") if isinstance(profile, dict) else None
            if isinstance(validation, dict) and validation.get("buildable") is True:
                push_buildable += 1
                if entry.get("matched_pipeline_template"):
                    push_buildable_matched += 1
                else:
                    push_buildable_fallback += 1

        return {
            "summary": {
                "templates_loaded": len(templates),
                "parsers_scanned": len(parsers),
                "converted_total": len(converted),
                "syslog_total": sum(1 for x in converted if x["ingestion_mode"] == "syslog"),
                "push_total": sum(1 for x in converted if x["ingestion_mode"] == "push"),
                "push_buildable_total": push_buildable,
                "push_non_buildable_total": max(len(push_entries) - push_buildable, 0),
                "push_buildable_matched_template_total": push_buildable_matched,
                "push_buildable_fallback_template_total": push_buildable_fallback,
                "used_archive_fallback": used_archive_fallback,
            },
            "converted": converted,
        }
