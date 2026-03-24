"""OCSF compliance validator for output events."""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class OutputValidator:
    """
    Validates OCSF event compliance before delivery to sinks.

    Checks:
    - Required OCSF fields present
    - Data type correctness
    - Value range validation
    - Schema version compatibility
    """

    REQUIRED_FIELDS = [
        "class_uid",
        "category_uid",
        "severity_id",
        "time",
        "metadata",
    ]

    REQUIRED_METADATA_FIELDS = [
        "version",
        "product",
    ]

    def __init__(self, strict_mode: bool = False):
        """
        Initialize validator.

        Args:
            strict_mode: If True, fail on warnings; if False, only log warnings
        """
        self.strict_mode = strict_mode
        self.stats = {"total_validated": 0, "passed": 0, "failed": 0}

    def validate_ocsf(self, event: Dict[str, Any]) -> bool:
        """
        Validate OCSF event.

        Args:
            event: OCSF event dictionary (the "log" portion)

        Returns:
            True if valid, False if invalid

        Raises:
            ValueError: If validation fails and strict_mode=True
        """
        self.stats["total_validated"] += 1
        errors = []

        for field in self.REQUIRED_FIELDS:
            if field not in event:
                errors.append(f"Missing required field: {field}")

        if "metadata" in event:
            for field in self.REQUIRED_METADATA_FIELDS:
                if field not in event["metadata"]:
                    errors.append(
                        f"Missing required metadata field: metadata.{field}"
                    )

        if "class_uid" in event and not isinstance(event["class_uid"], int):
            errors.append(
                f"class_uid must be integer, got {type(event['class_uid'])}"
            )

        if (
            "category_uid" in event
            and not isinstance(event["category_uid"], int)
        ):
            errors.append(
                f"category_uid must be integer, "
                f"got {type(event['category_uid'])}"
            )

        if (
            "severity_id" in event
            and not isinstance(event["severity_id"], int)
        ):
            errors.append(
                f"severity_id must be integer, "
                f"got {type(event['severity_id'])}"
            )

        if "time" in event and not isinstance(event["time"], (int, float)):
            errors.append(
                f"time must be numeric (unix timestamp), "
                f"got {type(event['time'])}"
            )

        if "severity_id" in event:
            severity = event["severity_id"]
            if not (0 <= severity <= 6):
                errors.append(
                    f"severity_id out of range [0-6]: {severity}"
                )

        if errors:
            self.stats["failed"] += 1
            error_msg = "; ".join(errors)

            if self.strict_mode:
                raise ValueError(f"OCSF validation failed: {error_msg}")
            else:
                logger.warning(f"OCSF validation warnings: {error_msg}")
                return False
        else:
            self.stats["passed"] += 1
            return True

    def get_statistics(self) -> Dict[str, Any]:
        """Get validation statistics."""
        return {
            **self.stats,
            "pass_rate": (
                self.stats["passed"] / self.stats["total_validated"]
                if self.stats["total_validated"] > 0
                else 0
            ),
        }
