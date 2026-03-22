"""
AI-SIEM Metadata Builder
Constructs complete metadata for pipeline.json

DIRECTOR REQUIREMENT 6: Add appropriate AI-SIEM metadata fields
Expands metadata to include all AI-SIEM-specific attributes:
- category, subcategory, vendor, product, log_type, etc.
- Documents source of each field (original parser vs. analysis vs. defaults)
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class AISIEMMetadataBuilder:
    """
    Builds comprehensive AI-SIEM metadata for pipelines

    TRACEABILITY:
    - Requirement 6: AI-SIEM metadata enrichment
    - All metadata fields sourced and documented
    - Propagates to both pipeline.json and GitHub metadata.json
    """

    # Vendor mappings for common log types
    VENDOR_MAPPINGS = {
        "windows": "Microsoft",
        "linux": "Linux Foundation",
        "azure": "Microsoft",
        "aws": "Amazon Web Services",
        "gcp": "Google",
        "office365": "Microsoft",
        "cisco": "Cisco Systems",
        "palo_alto": "Palo Alto Networks",
        "fortinet": "Fortinet",
        "checkpoint": "Check Point"
    }

    # Product mappings
    PRODUCT_MAPPINGS = {
        "windows": "Windows",
        "windows_security": "Windows Security Event Log",
        "windows_sysmon": "Windows Sysmon",
        "linux": "Linux",
        "linux_auth": "Linux Auth Log",
        "linux_syslog": "Linux Syslog",
        "azure_ad": "Azure Active Directory",
        "azure_activity": "Azure Activity Log",
        "aws_cloudtrail": "AWS CloudTrail",
        "aws_vpc": "AWS VPC Flow Logs",
        "office365": "Office 365",
        "cisco_asa": "Cisco ASA",
        "palo_alto_firewall": "Palo Alto Firewall"
    }

    # Log type categories
    LOG_TYPE_CATEGORIES = {
        "authentication": ["login", "logon", "auth", "authentication"],
        "network": ["firewall", "network", "traffic", "connection"],
        "security": ["security", "threat", "malware", "antivirus"],
        "system": ["system", "syslog", "event_log"],
        "application": ["application", "app", "software"],
        "cloud": ["azure", "aws", "gcp", "cloud"]
    }

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize metadata builder

        Args:
            config: Optional configuration
        """
        self.config = config or {}

    def build_complete_metadata(
        self,
        parser_id: str,
        parser_config: Dict[str, Any],
        analysis_data: Dict[str, Any],
        lua_code: str,
        conversion_metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Build complete metadata block for pipeline.json

        Args:
            parser_id: Parser identifier
            parser_config: Original S1 parser configuration
            analysis_data: Claude's analysis results
            lua_code: Generated LUA code
            conversion_metadata: Optional additional metadata

        Returns:
            Complete metadata dictionary

        REQUIREMENT 6: Comprehensive AI-SIEM metadata
        All fields documented with their source
        """
        logger.info(f"Building AI-SIEM metadata for: {parser_id}")

        metadata = {
            # Core identification
            "parser_id": parser_id,
            "created_at": datetime.now().isoformat(),
            "converter_version": "10.0.0",
            "conversion_method": "claude-rag-assisted",

            # Source information
            "source": self._build_source_metadata(parser_config),

            # Field information
            "fields": self._build_field_metadata(analysis_data, lua_code),

            # AI-SIEM specific metadata
            "ai_siem": self._build_ai_siem_metadata(
                parser_id,
                parser_config,
                analysis_data
            ),

            # OCSF mapping (if applicable)
            "ocsf": self._build_ocsf_metadata(analysis_data),

            # Quality metrics
            "quality": self._build_quality_metadata(
                analysis_data,
                lua_code,
                conversion_metadata
            ),

            # Deployment information
            "deployment": {
                "enabled": True,
                "deployment_target": "observo_pipeline",
                "requires_review": False
            }
        }

        # Add any additional metadata
        if conversion_metadata:
            metadata["additional"] = conversion_metadata

        logger.info(f"[OK] Metadata built with {len(metadata)} top-level sections")
        return metadata

    def _build_source_metadata(self, parser_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build source system metadata

        SOURCE DOCUMENTATION:
        - Extracted from original S1 parser configuration
        - Includes GitHub repository information
        """
        source_metadata = {
            "system": "sentinelone-ai-siem",
            "repository": "https://github.com/Sentinel-One/ai-siem",
            "repository_path": parser_config.get("repository_path", "unknown"),
            "source_type": parser_config.get("source_type", "community")
        }

        # Add original parser metadata if available
        if "metadata" in parser_config:
            original_metadata = parser_config["metadata"]
            source_metadata["original_metadata"] = original_metadata

            # Extract useful fields from original metadata
            if "author" in original_metadata:
                source_metadata["author"] = original_metadata["author"]
            if "version" in original_metadata:
                source_metadata["version"] = original_metadata["version"]
            if "description" in original_metadata:
                source_metadata["description"] = original_metadata["description"]

        return source_metadata

    def _build_field_metadata(
        self,
        analysis_data: Dict[str, Any],
        lua_code: str
    ) -> Dict[str, Any]:
        """
        Build field extraction metadata

        SOURCE DOCUMENTATION:
        - fields_extracted: From Claude analysis
        - field_count: Calculated from extracted fields
        - field_types: Inferred from analysis
        """
        fields_extracted = analysis_data.get("extracted_fields", [])
        if not fields_extracted and "field_mappings" in analysis_data:
            # Try to extract from field_mappings
            fields_extracted = list(analysis_data["field_mappings"].keys())

        field_metadata = {
            "fields_extracted": fields_extracted,
            "field_count": len(fields_extracted),
            "extraction_method": "claude_analysis"
        }

        # Add field types if available
        if "field_types" in analysis_data:
            field_metadata["field_types"] = analysis_data["field_types"]

        # Add field mappings if available
        if "field_mappings" in analysis_data:
            field_metadata["field_mappings"] = analysis_data["field_mappings"]

        return field_metadata

    def _build_ai_siem_metadata(
        self,
        parser_id: str,
        parser_config: Dict[str, Any],
        analysis_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build AI-SIEM specific metadata

        REQUIREMENT 6: AI-SIEM metadata fields
        SOURCE DOCUMENTATION:
        - category/subcategory: Inferred from parser_id and config
        - vendor/product: Mapped from known vendors
        - log_type: Extracted from parser configuration
        - priority: Default or from analysis
        """
        # Infer category and subcategory from parser_id
        category, subcategory = self._infer_category(parser_id, parser_config)

        # Infer vendor and product
        vendor = self._infer_vendor(parser_id, parser_config)
        product = self._infer_product(parser_id, parser_config)

        # Infer log type
        log_type = self._infer_log_type(parser_id, parser_config, analysis_data)

        ai_siem_metadata = {
            # Primary classification
            "category": category,
            "subcategory": subcategory,
            "vendor": vendor,
            "product": product,
            "log_type": log_type,

            # Additional classification
            "technology_type": self._infer_technology_type(parser_id),
            "data_source_type": self._infer_data_source_type(parser_id),

            # Priority and severity
            "priority": parser_config.get("priority", "medium"),
            "default_severity": "informational",

            # Use case tags
            "use_cases": self._infer_use_cases(parser_id, analysis_data),

            # Compliance frameworks
            "compliance_frameworks": self._infer_compliance_frameworks(category),

            # Source metadata documentation
            "_source_documentation": {
                "category": "inferred_from_parser_id",
                "vendor": "mapped_from_vendor_database",
                "product": "mapped_from_product_database",
                "log_type": "extracted_from_parser_config"
            }
        }

        return ai_siem_metadata

    def _infer_category(
        self,
        parser_id: str,
        parser_config: Dict[str, Any]
    ) -> tuple[str, str]:
        """
        Infer category and subcategory from parser ID

        Returns:
            Tuple of (category, subcategory)
        """
        parser_lower = parser_id.lower()

        # Category inference rules
        if any(keyword in parser_lower for keyword in ["windows", "linux", "macos"]):
            category = "operating_system"
            if "security" in parser_lower or "auth" in parser_lower:
                subcategory = "security"
            elif "syslog" in parser_lower or "system" in parser_lower:
                subcategory = "system"
            else:
                subcategory = "general"

        elif any(keyword in parser_lower for keyword in ["firewall", "network", "traffic"]):
            category = "network"
            if "firewall" in parser_lower:
                subcategory = "firewall"
            else:
                subcategory = "traffic"

        elif any(keyword in parser_lower for keyword in ["azure", "aws", "gcp", "office365"]):
            category = "cloud"
            if "azure" in parser_lower:
                subcategory = "azure"
            elif "aws" in parser_lower:
                subcategory = "aws"
            elif "gcp" in parser_lower:
                subcategory = "gcp"
            else:
                subcategory = "office365"

        elif any(keyword in parser_lower for keyword in ["application", "app", "web"]):
            category = "application"
            subcategory = "web" if "web" in parser_lower else "general"

        else:
            category = "general"
            subcategory = "other"

        return category, subcategory

    def _infer_vendor(
        self,
        parser_id: str,
        parser_config: Dict[str, Any]
    ) -> str:
        """Infer vendor from parser ID"""
        parser_lower = parser_id.lower()

        for keyword, vendor in self.VENDOR_MAPPINGS.items():
            if keyword in parser_lower:
                return vendor

        # Check metadata
        if "metadata" in parser_config:
            metadata = parser_config["metadata"]
            if "vendor" in metadata:
                return metadata["vendor"]

        return "Unknown"

    def _infer_product(
        self,
        parser_id: str,
        parser_config: Dict[str, Any]
    ) -> str:
        """Infer product from parser ID"""
        parser_lower = parser_id.lower()

        # Try exact matches first
        for keyword, product in self.PRODUCT_MAPPINGS.items():
            if keyword in parser_lower:
                return product

        # Check metadata
        if "metadata" in parser_config:
            metadata = parser_config["metadata"]
            if "product" in metadata:
                return metadata["product"]

        # Fallback: use parser_id as product name
        return parser_id.replace("_", " ").title()

    def _infer_log_type(
        self,
        parser_id: str,
        parser_config: Dict[str, Any],
        analysis_data: Dict[str, Any]
    ) -> str:
        """Infer log type from parser configuration"""
        # Check parser config first
        if "log_type" in parser_config:
            return parser_config["log_type"]

        if "config" in parser_config and isinstance(parser_config["config"], dict):
            config = parser_config["config"]
            if "log_type" in config:
                return config["log_type"]
            if "event_type" in config:
                return config["event_type"]

        # Infer from parser_id
        parser_lower = parser_id.lower()
        for log_type, keywords in self.LOG_TYPE_CATEGORIES.items():
            if any(keyword in parser_lower for keyword in keywords):
                return log_type

        return "unknown"

    def _infer_technology_type(self, parser_id: str) -> str:
        """Infer technology type (endpoint, network, cloud, etc.)"""
        parser_lower = parser_id.lower()

        if any(k in parser_lower for k in ["windows", "linux", "macos", "endpoint"]):
            return "endpoint"
        elif any(k in parser_lower for k in ["firewall", "router", "switch", "network"]):
            return "network"
        elif any(k in parser_lower for k in ["azure", "aws", "gcp", "cloud"]):
            return "cloud"
        elif any(k in parser_lower for k in ["web", "application", "app"]):
            return "application"
        else:
            return "other"

    def _infer_data_source_type(self, parser_id: str) -> str:
        """Infer data source type (logs, metrics, traces, etc.)"""
        # Most S1 parsers are for logs
        return "logs"

    def _infer_use_cases(
        self,
        parser_id: str,
        analysis_data: Dict[str, Any]
    ) -> List[str]:
        """Infer security use cases"""
        use_cases = []
        parser_lower = parser_id.lower()

        if any(k in parser_lower for k in ["auth", "login", "logon"]):
            use_cases.append("authentication_monitoring")
        if any(k in parser_lower for k in ["firewall", "network"]):
            use_cases.append("network_monitoring")
        if any(k in parser_lower for k in ["security", "threat", "malware"]):
            use_cases.append("threat_detection")
        if any(k in parser_lower for k in ["cloud", "azure", "aws"]):
            use_cases.append("cloud_security")

        # Add MITRE ATT&CK if mentioned in analysis
        if "mitre" in str(analysis_data).lower():
            use_cases.append("mitre_attack_mapping")

        return use_cases if use_cases else ["general_monitoring"]

    def _infer_compliance_frameworks(self, category: str) -> List[str]:
        """Infer applicable compliance frameworks"""
        frameworks = []

        # All logs support general compliance
        frameworks.append("general_compliance")

        if category in ["cloud", "network"]:
            frameworks.extend(["pci_dss", "nist_csf"])

        if category == "operating_system":
            frameworks.extend(["cis_benchmarks", "stig"])

        return frameworks

    def _build_ocsf_metadata(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build OCSF (Open Cybersecurity Schema Framework) metadata

        SOURCE DOCUMENTATION:
        - Extracted from Claude analysis if OCSF mapping was performed
        """
        ocsf_metadata = {}

        if "ocsf" in analysis_data:
            ocsf_metadata = analysis_data["ocsf"]
        elif "ocsf_mapping" in analysis_data:
            ocsf_metadata = analysis_data["ocsf_mapping"]

        # Add defaults if not present
        if not ocsf_metadata:
            ocsf_metadata = {
                "class_name": "Unknown",
                "category_name": "Unknown",
                "mapped": False
            }

        return ocsf_metadata

    def _build_quality_metadata(
        self,
        analysis_data: Dict[str, Any],
        lua_code: str,
        conversion_metadata: Optional[Dict]
    ) -> Dict[str, Any]:
        """
        Build quality and confidence metrics

        SOURCE DOCUMENTATION:
        - complexity: From parser configuration
        - confidence_score: From Claude analysis
        - rag_assisted: From conversion process
        """
        quality_metadata = {
            "complexity": analysis_data.get("complexity", "medium"),
            "confidence_score": analysis_data.get("confidence_score", 0.8),
            "rag_assisted": True if conversion_metadata and conversion_metadata.get("rag_used") else False,
            "human_reviewed": False,
            "lua_code_size": len(lua_code),
            "analysis_timestamp": datetime.now().isoformat()
        }

        # Add conversion metrics if available
        if conversion_metadata:
            if "generation_time" in conversion_metadata:
                quality_metadata["generation_time_seconds"] = conversion_metadata["generation_time"]
            if "rag_examples_used" in conversion_metadata:
                quality_metadata["rag_examples_used"] = conversion_metadata["rag_examples_used"]

        return quality_metadata
