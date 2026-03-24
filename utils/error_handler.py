"""
Error handling utilities for the conversion system
"""
from typing import Optional, Dict, Any, Callable
from functools import wraps
import time
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


logger = logging.getLogger(__name__)


class ConversionError(Exception):
    """Base exception for conversion system errors"""
    pass


class ParserScanError(ConversionError):
    """Error scanning parsers from GitHub"""
    pass


class ClaudeAPIError(ConversionError):
    """Error interacting with Claude API"""
    pass


class ObservoAPIError(ConversionError):
    """Error interacting with Observo.ai API"""
    pass


class LuaGenerationError(ConversionError):
    """Error generating LUA code"""
    pass


class DeploymentError(ConversionError):
    """Error deploying pipeline to Observo.ai"""
    pass


class ValidationError(ConversionError):
    """Error validating parser or pipeline configuration"""
    pass


def handle_api_errors(api_name: str):
    """Decorator for handling API errors with retries"""
    def decorator(func: Callable):
        @wraps(func)
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=4, max=60),
            retry=retry_if_exception_type((ConnectionError, TimeoutError)),
            before_sleep=lambda retry_state: logger.warning(
                f"Retrying {api_name} API call, attempt {retry_state.attempt_number}"
            )
        )
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"{api_name} API error in {func.__name__}: {str(e)}")
                if api_name == "Claude":
                    raise ClaudeAPIError(f"Claude API error: {str(e)}")
                elif api_name == "Observo":
                    raise ObservoAPIError(f"Observo API error: {str(e)}")
                elif api_name == "GitHub":
                    raise ParserScanError(f"GitHub API error: {str(e)}")
                else:
                    raise ConversionError(f"{api_name} error: {str(e)}")
        return wrapper
    return decorator


def safe_json_parse(json_str: str, default: Optional[Dict] = None) -> Dict:
    """Safely parse JSON with fallback"""
    import json
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"JSON parse error: {e}, returning default")
        return default or {}


def validate_parser_config(config: Dict) -> bool:
    """Validate parser configuration structure"""
    required_fields = ["attributes", "formats", "mappings"]
    for field in required_fields:
        if field not in config:
            logger.error(f"Missing required field in parser config: {field}")
            return False
    return True


def validate_lua_code(lua_code: str) -> bool:
    """Basic validation of generated LUA code"""
    required_patterns = [
        "function transform",
        "return output",
        "class_uid",
    ]
    for pattern in required_patterns:
        if pattern not in lua_code:
            logger.error(f"Missing required pattern in LUA code: {pattern}")
            return False
    return True


class ErrorRecovery:
    """Error recovery strategies for the conversion system"""

    @staticmethod
    def recover_from_claude_error(parser_info: Dict) -> Dict:
        """Generate fallback analysis when Claude fails"""
        logger.warning("Using fallback parser analysis due to Claude error")
        return {
            "semantic_summary": f"Parser for {parser_info.get('name', 'unknown')}",
            "parser_complexity": {
                "level": "Medium",
                "factors": ["Unable to analyze with Claude"],
                "confidence": 0.5
            },
            "field_mappings": {},
            "ocsf_classification": {
                "class_uid": 0,
                "class_name": "Unknown",
                "category_uid": 0,
                "category_name": "Unknown",
                "confidence": 0.3
            },
            "overall_confidence": 0.4
        }

    @staticmethod
    def generate_basic_lua(parser_info: Dict) -> str:
        """Generate basic LUA transformation when advanced generation fails"""
        logger.warning("Using basic LUA template due to generation error")
        return f"""-- Basic transformation for {parser_info.get('name', 'unknown')}
-- Auto-generated fallback template

function transform(record)
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    local output = {{
        class_uid = 0,
        class_name = "Unknown",
        raw_data = record
    }}

    -- Basic field copy
    for key, value in pairs(record) do
        output[key] = value
    end

    return output
end
"""


class RateLimiter:
    """Rate limiting utility for API calls"""

    def __init__(self, calls_per_second: float = 1.0):
        self.delay = 1.0 / calls_per_second
        self.last_call = 0

    async def wait(self):
        """Wait if necessary to respect rate limit"""
        import asyncio
        elapsed = time.time() - self.last_call
        if elapsed < self.delay:
            await asyncio.sleep(self.delay - elapsed)
        self.last_call = time.time()