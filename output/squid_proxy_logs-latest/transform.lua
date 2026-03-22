--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: squid_proxy_logs-latest
  Generated: 2025-10-13T12:34:07.907903
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: squid_proxy_logs-latest 
-- OCSF Class: HTTP Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:03:55.799839

-- Pre-declare locals for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_format = string.format
local ipairs = ipairs

-- Validation patterns
local PATTERNS = {
    ip = "^%d+%.%d+%.%d+%.%d+$",
    method = "^[A-Z]+$",
    url = "^https?://"
}

-- IP address cache for repeated lookups
local ip_cache = {}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local reference
    local output = {
        class_uid = 1001,
        class_name = "HTTP Activity", 
        category_uid = 1,
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = 100101,
        http = {},
        src_endpoint = {}
    }

    -- Timestamp handling with validation
    if record.timestamp then
        local ts = tonumber(record.timestamp)
        if ts then
            output.time = ts
        else
            output.time = os_time() * 1000
        end
    else
        output.time = os_time() * 1000
    end

    -- IP address handling with caching
    if record.remotehost then
        local cached_ip = ip_cache[record.remotehost]
        if cached_ip then
            output.src_endpoint.ip = cached_ip
        else
            -- Basic IP validation
            if record.remotehost:match(PATTERNS.ip) then
                output.src_endpoint.ip = record.remotehost
                ip_cache[record.remotehost] = record.remotehost
            end
        end
    end

    -- HTTP method validation and normalization
    if record.method then
        local method = record.method:upper()
        if method:match(PATTERNS.method) then
            output.http.method = method
        end
    end

    -- URL handling with basic validation
    if record.url then
        if record.url:match(PATTERNS.url) then
            output.http.url = record.url
        else
            -- Attempt to normalize URL
            output.http.url = string_format("http://%s", record.url)
        end
    end

    -- Status code handling with type conversion
    if record.status then
        local status = tonumber(record.status)
        if status and status >= 100 and status < 600 then
            output.http.status_code = status
        end
    end

    -- Additional fields with validation
    if record.bytes then
        local bytes = tonumber(record.bytes)
        if bytes then
            output.http.bytes = bytes
        end
    end

    -- Final validation of required fields
    if not output.http.method or not output.http.url then
        return nil, "Missing required HTTP fields"
    end

    return output
end

-- Error recovery function
local function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end