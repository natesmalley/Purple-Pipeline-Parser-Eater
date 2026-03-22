--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: zscaler_zia_logs-latest
  Generated: 2025-10-13T12:42:14.749198
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: zscaler_zia_logs-latest 
-- OCSF Class: Web Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:05:29.971169

-- Pre-compile patterns for performance
local URL_PATTERN = "|^(.-)^|"
local TIMESTAMP_FORMAT = "(%d+)"

-- Cached string operations
local string_match = string.match
local string_format = string.format
local tonumber = tonumber

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local variables
    local output = {
        class_uid = 1001,
        class_name = "Web Activity", 
        category_uid = 1,
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = 100101,
        metadata = {},
        security_result = {},
        http = {}
    }

    -- Timestamp transformation with validation
    local timestamp = record.timestamp
    if timestamp then
        local ts = tonumber(string_match(timestamp, TIMESTAMP_FORMAT))
        if ts then
            output.time = ts * 1000 -- Convert to milliseconds
        end
    end

    -- URL extraction and transformation
    local url = record.url
    if url then
        local extracted_url = string_match(url, URL_PATTERN)
        if extracted_url then
            output.http.url = extracted_url
        end
    end

    -- Action mapping with validation
    local action = record.action
    if action then
        output.security_result.action = action
    end

    -- Additional field mappings
    if record.host then
        output.http.host = record.host
    end
    
    if record.reqmethod then
        output.http.method = record.reqmethod
    end

    if record.respcode then
        output.http.response_code = tonumber(record.respcode)
    end

    -- Enrich metadata
    output.metadata.product = {
        name = "Zscaler Internet Access",
        vendor_name = "Zscaler"
    }

    -- Validation and cleanup
    if not output.time then
        output.time = os.time() * 1000
    end

    -- Required field validation
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Missing required class_uid"
    end

    -- Size validation for large fields
    if output.http.url and #output.http.url > 2048 then
        output.http.url = string_format("%s...[truncated]", 
            string.sub(output.http.url, 1, 2045))
    end

    return output
end

-- Error handler wrapper
function safe_transform(record)
    local status, result = pcall(transform, record)
    if not status then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end

-- Cache for repeated values
local value_cache = {}
local function get_cached_value(key)
    if not value_cache[key] then
        value_cache[key] = string_format("cached_%s", key)
    end
    return value_cache[key]
end

-- Test cases
--[[ 
local test1 = safe_transform({
    timestamp = "1634567890",
    url = "|^https://example.com^|",
    action = "allow"
})

local test2 = safe_transform(nil)

local test3 = safe_transform({})
--]]