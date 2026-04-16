#!/usr/bin/env python3
"""
Secret Management Utility

Manages secret lifecycle: expiration, rotation, validation.

SECURITY FIX: Phase 7 - Secret Rotation Mechanism
- Tracks secret expiration dates
- Warns about secrets nearing expiration
- Enforces rotation in production
"""

import os
import logging
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)


@dataclass
class SecretMetadata:
    """Metadata about a secret"""
    name: str
    created_at: str
    expires_at: Optional[str]
    rotated_at: Optional[str]
    rotation_days: int
    last_warning: Optional[str] = field(default=None)


class SecretManager:
    """
    Manages secret lifecycle and rotation.

    Features:
    - Secret expiration tracking
    - Rotation reminders
    - Expiration warnings
    - Rotation history
    """

    DEFAULT_ROTATION_DAYS = 90

    def __init__(self, metadata_file: Optional[Path] = None):
        """
        Initialize secret manager.

        Args:
            metadata_file: Path to store secret metadata (default: data/secret_metadata.json)
        """
        if metadata_file is None:
            metadata_file = Path("data/secret_metadata.json")

        self.metadata_file = metadata_file
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        self._metadata: Dict[str, SecretMetadata] = self._load_metadata()

    def _load_metadata(self) -> Dict[str, SecretMetadata]:
        """Load secret metadata from file"""
        if not self.metadata_file.exists():
            return {}

        try:
            with open(self.metadata_file, 'r') as f:
                data = json.load(f)
                return {
                    name: SecretMetadata(**meta)
                    for name, meta in data.items()
                }
        except Exception as e:
            logger.warning(f"Could not load secret metadata: {e}")
            return {}

    def _save_metadata(self):
        """Save secret metadata to file"""
        try:
            data = {
                name: asdict(meta)
                for name, meta in self._metadata.items()
            }
            with open(self.metadata_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save secret metadata: {e}")

    def register_secret(
        self,
        name: str,
        rotation_days: int = None,
        created_at: Optional[datetime] = None
    ):
        """
        Register a secret for tracking.

        Args:
            name: Secret name (e.g., 'ANTHROPIC_API_KEY')
            rotation_days: Days until rotation required (default: 90)
            created_at: When secret was created (default: now)
        """
        rotation_days = rotation_days or self.DEFAULT_ROTATION_DAYS
        created_at = created_at or datetime.now(timezone.utc)
        expires_at = created_at + timedelta(days=rotation_days)

        if name not in self._metadata:
            self._metadata[name] = SecretMetadata(
                name=name,
                created_at=created_at.isoformat(),
                expires_at=expires_at.isoformat(),
                rotated_at=None,
                rotation_days=rotation_days
            )
            self._save_metadata()
            logger.info(f"Registered secret: {name} (expires: {expires_at.date()})")

    def check_secret_expiration(self, name: str) -> Tuple[bool, Optional[str]]:
        """
        Check if secret is expired or nearing expiration.

        Returns:
            Tuple of (is_valid, warning_message)
        """
        if name not in self._metadata:
            # Secret not registered - register it now
            self.register_secret(name)
            return True, None

        meta = self._metadata[name]

        if not meta.expires_at:
            return True, None

        expires_at = datetime.fromisoformat(meta.expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        days_until_expiry = (expires_at - now).days

        if days_until_expiry < 0:
            return False, f"Secret {name} expired {abs(days_until_expiry)} days ago"

        if days_until_expiry <= 7:
            return True, f"Secret {name} expires in {days_until_expiry} days - rotate soon!"

        if days_until_expiry <= 30:
            # Warn once per week
            last_warning = datetime.fromisoformat(meta.last_warning) if meta.last_warning else None
            if last_warning is not None and last_warning.tzinfo is None:
                last_warning = last_warning.replace(tzinfo=timezone.utc)
            if not last_warning or (now - last_warning).days >= 7:
                meta.last_warning = now.isoformat()
                self._save_metadata()
                return True, f"Secret {name} expires in {days_until_expiry} days"

        return True, None

    def rotate_secret(self, name: str, new_secret: Optional[str] = None):
        """
        Mark secret as rotated.

        Args:
            name: Secret name
            new_secret: New secret value (optional, for validation)
        """
        if name not in self._metadata:
            self.register_secret(name)

        meta = self._metadata[name]
        meta.rotated_at = datetime.now(timezone.utc).isoformat()
        meta.created_at = datetime.now(timezone.utc).isoformat()

        # Calculate new expiration
        expires_at = datetime.now(timezone.utc) + timedelta(days=meta.rotation_days)
        meta.expires_at = expires_at.isoformat()
        meta.last_warning = None

        self._save_metadata()
        logger.info(f"Secret {name} rotated (new expiration: {expires_at.date()})")

    def validate_all_secrets(self) -> Dict[str, Tuple[bool, Optional[str]]]:
        """
        Validate all registered secrets.

        Returns:
            Dict mapping secret name to (is_valid, warning)
        """
        results = {}

        # Check all registered secrets
        for name in self._metadata.keys():
            is_valid, warning = self.check_secret_expiration(name)
            results[name] = (is_valid, warning)

            if warning:
                if is_valid:
                    logger.warning(f"Secret warning: {warning}")
                else:
                    logger.error(f"Secret expired: {warning}")

        return results
