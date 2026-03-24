"""Manifest schema validation via Pydantic."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ManifestVersion(BaseModel):
    lua_sha256: str = Field(..., description="SHA256 hash of transform.lua")
    semantic: str = Field(..., description="Semantic version string")
    previous: Optional[str] = Field(None, description="Previous semantic version")
    changelog: List[str] = Field(default_factory=list)


class Compatibility(BaseModel):
    min_dataplane_version: str = Field(...)
    ocsf_version: str = Field(...)


class LuaMetadata(BaseModel):
    file: str = Field(default="transform.lua")
    entry_function: str = Field(default="processEvent")
    search_dirs: List[str] = Field(default_factory=list)
    estimated_memory_mb: Optional[float] = Field(default=None)
    avg_execution_time_ms: Optional[float] = Field(default=None)


class OCSFOutput(BaseModel):
    class_uid: int
    class_name: str
    extracted_fields: List[str] = Field(default_factory=list)


class SourceMetadata(BaseModel):
    repository: str
    parser_path: Optional[str] = None
    git_commit: Optional[str] = None


class DeploymentMetadata(BaseModel):
    deployed_at: datetime
    deployed_by: str
    environment: str
    canary_percentage: int = Field(default=100)


class ParserManifest(BaseModel):
    manifest_version: str = Field(default="1.0")
    parser_id: str
    version: ManifestVersion
    generated_at: datetime
    compatibility: Optional[Compatibility] = None
    lua_metadata: Optional[LuaMetadata] = None
    ocsf_output: Optional[OCSFOutput] = None
    source: Optional[SourceMetadata] = None
    deployment: Optional[DeploymentMetadata] = None


def validate_manifest(manifest: dict) -> ParserManifest:
    """Validate manifest dict and return model."""

    return ParserManifest.parse_obj(manifest)

