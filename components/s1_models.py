"""
SentinelOne API Models and Schema Validation
Comprehensive models for S1 query language, OCSF schemas, and SDL API
"""
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import re


# ============================================================================
# Query Language Models
# ============================================================================

class S1Operator(Enum):
    """SentinelOne query operators"""
    # Comparison operators
    EQUALS = "="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="

    # String operators
    CONTAINS = "CONTAINS"
    STARTS_WITH = "STARTSWITH"
    ENDS_WITH = "ENDSWITH"
    LIKE = "LIKE"
    MATCHES = "MATCHES"

    # List operators
    IN = "IN"
    NOT_IN = "NOT IN"

    # Logical operators
    AND = "AND"
    OR = "OR"
    NOT = "NOT"

    # Existence operators
    EXISTS = "EXISTS"
    NOT_EXISTS = "NOT EXISTS"
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"


class S1DataType(Enum):
    """SentinelOne field data types"""
    STRING = "String"
    INTEGER = "Int"
    LONG = "Long"
    BOOLEAN = "Boolean"
    DATETIME = "DateTime"
    JSON = "JSON"
    FLOAT = "Float"
    UUID = "UUID"
    ENUM = "Enum"


class S1QueryType(Enum):
    """Types of S1 queries"""
    EVENT_SEARCH = "event_search"
    DEEP_VISIBILITY = "deep_visibility"
    GRAPHQL = "graphql"
    POWER_QUERY = "power_query"
    SDL_QUERY = "sdl_query"


@dataclass
class S1Field:
    """SentinelOne field definition"""
    name: str
    data_type: S1DataType
    description: str = ""
    mandatory: bool = False
    searchable: bool = True
    graphql_path: Optional[str] = None
    ocsf_mapping: Optional[str] = None
    example_values: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate field definition"""
        if not self.name:
            raise ValueError("Field name cannot be empty")
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', self.name):
            raise ValueError(f"Invalid field name: {self.name}")


@dataclass
class S1QueryCondition:
    """Single query condition"""
    field: str
    operator: S1Operator
    value: Union[str, int, float, bool, List[Any]]
    negated: bool = False

    def to_s1_syntax(self) -> str:
        """Convert to S1 query syntax"""
        neg = "NOT " if self.negated else ""

        if self.operator in [S1Operator.IN, S1Operator.NOT_IN]:
            values = ', '.join([f'"{v}"' if isinstance(v, str) else str(v) for v in self.value])
            return f"{neg}{self.field} {self.operator.value} ({values})"
        elif isinstance(self.value, str):
            return f'{neg}{self.field} {self.operator.value} "{self.value}"'
        else:
            return f'{neg}{self.field} {self.operator.value} {self.value}'

    def to_observo_filter(self) -> Dict[str, Any]:
        """Convert to Observo filter format"""
        # This will be enhanced with actual Observo field mappings
        return {
            "field": self.field,
            "operator": self._map_operator_to_observo(),
            "value": self.value
        }

    def _map_operator_to_observo(self) -> str:
        """Map S1 operator to Observo operator"""
        operator_map = {
            S1Operator.EQUALS: "==",
            S1Operator.NOT_EQUALS: "!=",
            S1Operator.GREATER_THAN: ">",
            S1Operator.LESS_THAN: "<",
            S1Operator.GREATER_EQUAL: ">=",
            S1Operator.LESS_EQUAL: "<=",
            S1Operator.CONTAINS: "contains",
            S1Operator.STARTS_WITH: "startswith",
            S1Operator.ENDS_WITH: "endswith",
            S1Operator.IN: "in",
            S1Operator.NOT_IN: "not in"
        }
        return operator_map.get(self.operator, "==")


@dataclass
class S1Query:
    """Complete SentinelOne query"""
    conditions: List[S1QueryCondition] = field(default_factory=list)
    query_type: S1QueryType = S1QueryType.EVENT_SEARCH
    time_range: Optional[Dict[str, datetime]] = None
    aggregations: List[str] = field(default_factory=list)
    group_by: List[str] = field(default_factory=list)
    sort_by: List[Dict[str, str]] = field(default_factory=list)
    limit: Optional[int] = None
    raw_query: Optional[str] = None

    def to_s1_syntax(self) -> str:
        """Convert to S1 query syntax"""
        if self.raw_query:
            return self.raw_query

        condition_strings = [cond.to_s1_syntax() for cond in self.conditions]
        query = " AND ".join(condition_strings)

        # Add time range if present
        if self.time_range:
            start = self.time_range.get('start')
            end = self.time_range.get('end')
            if start:
                query += f' AND timestamp >= "{start.isoformat()}"'
            if end:
                query += f' AND timestamp <= "{end.isoformat()}"'

        # Add aggregations
        if self.aggregations:
            agg_str = ", ".join(self.aggregations)
            query += f" | {agg_str}"

        # Add group by
        if self.group_by:
            group_str = ", ".join(self.group_by)
            query += f" | GROUP BY {group_str}"

        return query


# ============================================================================
# OCSF Models
# ============================================================================

class OCSFCategory(Enum):
    """OCSF event categories"""
    SYSTEM_ACTIVITY = "System Activity"
    NETWORK_ACTIVITY = "Network Activity"
    FINDINGS = "Findings"
    IDENTITY_ACCESS = "Identity & Access Management"
    APPLICATION_ACTIVITY = "Application Activity"
    DISCOVERY = "Discovery"


@dataclass
class OCSFField:
    """OCSF standardized field"""
    ocsf_name: str
    ocsf_path: str
    data_type: str
    description: str
    s1_mapping: Optional[str] = None
    observo_mapping: Optional[str] = None
    required: bool = False


@dataclass
class OCSFEvent:
    """OCSF event structure"""
    class_uid: int
    class_name: str
    category: OCSFCategory
    severity_id: int
    activity_id: int
    type_uid: int
    fields: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# SDL API Models
# ============================================================================

@dataclass
class SDLQueryRequest:
    """SDL API query request"""
    query_type: str = "log"
    filter: str = ""
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    max_count: int = 100
    page_mode: str = "head"
    columns: Optional[str] = None
    continuation_token: Optional[str] = None
    priority: str = "low"


@dataclass
class SDLPowerQuery:
    """SDL PowerQuery request"""
    query: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    priority: str = "low"


@dataclass
class SDLEvent:
    """SDL event structure"""
    timestamp: str
    severity: int
    thread: Optional[str] = None
    attrs: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# GraphQL Models
# ============================================================================

@dataclass
class GraphQLQuery:
    """GraphQL query structure"""
    operation: str  # query or mutation
    query_name: str
    fields: List[str] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    pagination: Optional[Dict[str, Any]] = None


@dataclass
class GraphQLType:
    """GraphQL type definition"""
    name: str
    fields: Dict[str, Dict[str, str]] = field(default_factory=dict)
    description: str = ""
    is_input: bool = False
    is_enum: bool = False


# ============================================================================
# Field Mapping Models
# ============================================================================

@dataclass
class FieldMapping:
    """Mapping between different field naming conventions"""
    s1_field: str
    observo_field: str
    ocsf_field: Optional[str] = None
    transformation: Optional[str] = None
    data_type_mapping: Optional[Dict[str, str]] = None
    notes: str = ""

    def apply_transformation(self, value: Any) -> Any:
        """Apply transformation to field value"""
        if not self.transformation:
            return value

        # Define common transformations
        transformations = {
            "lowercase": lambda v: v.lower() if isinstance(v, str) else v,
            "uppercase": lambda v: v.upper() if isinstance(v, str) else v,
            "timestamp_ms_to_s": lambda v: v / 1000 if isinstance(v, (int, float)) else v,
            "timestamp_s_to_ms": lambda v: v * 1000 if isinstance(v, (int, float)) else v,
            "bool_to_int": lambda v: 1 if v else 0,
            "int_to_bool": lambda v: bool(v),
            "json_stringify": lambda v: str(v) if not isinstance(v, str) else v,
        }

        transform_func = transformations.get(self.transformation)
        if transform_func:
            return transform_func(value)

        return value


@dataclass
class MappingRule:
    """Complete mapping rule for S1 to Observo conversion"""
    rule_id: str
    name: str
    source_query: str
    target_format: str
    field_mappings: List[FieldMapping] = field(default_factory=list)
    operator_mappings: Dict[str, str] = field(default_factory=dict)
    aggregation_mappings: Dict[str, str] = field(default_factory=dict)
    examples: List[Dict[str, str]] = field(default_factory=list)
    confidence_score: float = 1.0


# ============================================================================
# Vulnerability Models
# ============================================================================

@dataclass
class VulnerabilityField:
    """Vulnerability data dictionary field"""
    attribute: str
    data_type: str
    mandatory: bool
    data_source: str
    graphql_detail_field: Optional[str] = None
    graphql_list_field: Optional[str] = None
    available_in_event_search: bool = False
    displayed_in_details: bool = False
    table_column: Optional[str] = None


@dataclass
class Vulnerability:
    """Vulnerability finding"""
    id: str
    external_id: str
    name: str
    severity: str
    status: str
    detected_at: datetime
    vendor: str
    product: str
    software_name: str
    software_version: str
    cve_id: Optional[str] = None
    cve_score: Optional[float] = None
    asset_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Validation Functions
# ============================================================================

class S1QueryValidator:
    """Validator for S1 queries"""

    @staticmethod
    def validate_field_name(field_name: str) -> bool:
        """Validate S1 field name syntax"""
        return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', field_name))

    @staticmethod
    def validate_operator(field_type: S1DataType, operator: S1Operator) -> bool:
        """Validate operator for field type"""
        string_operators = [
            S1Operator.EQUALS, S1Operator.NOT_EQUALS,
            S1Operator.CONTAINS, S1Operator.STARTS_WITH,
            S1Operator.ENDS_WITH, S1Operator.LIKE,
            S1Operator.IN, S1Operator.NOT_IN
        ]

        numeric_operators = [
            S1Operator.EQUALS, S1Operator.NOT_EQUALS,
            S1Operator.GREATER_THAN, S1Operator.LESS_THAN,
            S1Operator.GREATER_EQUAL, S1Operator.LESS_EQUAL,
            S1Operator.IN, S1Operator.NOT_IN
        ]

        boolean_operators = [
            S1Operator.EQUALS, S1Operator.NOT_EQUALS
        ]

        if field_type == S1DataType.STRING:
            return operator in string_operators
        elif field_type in [S1DataType.INTEGER, S1DataType.LONG, S1DataType.FLOAT]:
            return operator in numeric_operators
        elif field_type == S1DataType.BOOLEAN:
            return operator in boolean_operators
        else:
            return True  # Allow all operators for other types

    @staticmethod
    def validate_query_syntax(query: str) -> Tuple[bool, List[str]]:
        """Validate S1 query syntax"""
        errors = []

        # Check for balanced parentheses
        if query.count('(') != query.count(')'):
            errors.append("Unbalanced parentheses")

        # Check for balanced quotes
        if query.count('"') % 2 != 0:
            errors.append("Unbalanced quotes")

        # Check for valid operators
        invalid_operators = re.findall(r'(\w+)\s+(INVALID)', query, re.IGNORECASE)
        if invalid_operators:
            errors.append(f"Invalid operators: {invalid_operators}")

        return len(errors) == 0, errors


# ============================================================================
# Converter Functions
# ============================================================================

class S1ToObservoConverter:
    """Convert S1 queries to Observo format"""

    def __init__(self, field_mappings: List[FieldMapping]):
        """
        Initialize converter

        Args:
            field_mappings: List of field mapping rules
        """
        self.field_mappings = {m.s1_field: m for m in field_mappings}

    def convert_query(self, s1_query: S1Query) -> Dict[str, Any]:
        """
        Convert S1 query to Observo format

        Args:
            s1_query: SentinelOne query

        Returns:
            Observo pipeline configuration
        """
        observo_filters = []

        for condition in s1_query.conditions:
            # Map field name
            mapping = self.field_mappings.get(condition.field)
            if mapping:
                observo_field = mapping.observo_field
                # Apply transformation if needed
                value = mapping.apply_transformation(condition.value)
            else:
                # No mapping found, use original field
                observo_field = condition.field
                value = condition.value

            observo_filters.append({
                "field": observo_field,
                "operator": condition._map_operator_to_observo(),
                "value": value
            })

        return {
            "filters": observo_filters,
            "aggregations": s1_query.aggregations,
            "group_by": s1_query.group_by,
            "time_range": s1_query.time_range,
            "limit": s1_query.limit
        }

    def convert_field_value(self, s1_field: str, value: Any) -> Tuple[str, Any]:
        """
        Convert S1 field and value to Observo format

        Args:
            s1_field: S1 field name
            value: Field value

        Returns:
            Tuple of (observo_field, converted_value)
        """
        mapping = self.field_mappings.get(s1_field)
        if mapping:
            return mapping.observo_field, mapping.apply_transformation(value)
        return s1_field, value
