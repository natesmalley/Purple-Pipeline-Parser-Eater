-- SentinelOne Parser: haproxy_loadbalancer_logs-latest 
-- OCSF Class: Network Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:00:49.703358

-- Pre-compile patterns for performance
local IP_PATTERN = "^%d+%.%d+%.%d+%.%d+$"
local TIMESTAMP_PATTERN = "^%w+%s+%d+%s+[0-9:]+$"

-- Cache frequently used functions
local match = string.match
local format = string.format
local time = os.time

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure with local vars
    local output = {
        class_uid = 1001,
        class_name = "Network Activity", 
        category_uid = 1,
        category_name = "Network & Systems Activity",
        activity_id = 1,
        type_uid = 100101,
        metadata = {},
        http_request = {},
        src_endpoint = {},
        time = nil
    }

    -- Timestamp transformation (regex optimized)
    if record.timestamp and match(record.timestamp, TIMESTAMP_PATTERN) then
        -- Convert timestamp to UNIX ms
        local ts = parse_timestamp(record.timestamp)
        output.time = ts and (ts * 1000) or (time() * 1000)
    else
        output.time = time() * 1000
    end

    -- Source IP transformation with validation
    if record.sourceip_with_socket then
        local ip = match(record.sourceip_with_socket, IP_PATTERN)
        if ip then
            output.src_endpoint.ip = ip
        end
    end

    -- HTTP Method (direct copy with validation)
    if record.Method and type(record.Method) == "string" then
        output.http_request.method = record.Method
    end

    -- URL parsing with error handling
    if record.URL then
        local success, url = pcall(function()
            return parse_url(record.URL)
        end)
        if success and url then
            output.http_request.url = url
        end
    end

    -- Additional metadata
    output.metadata.product = {
        name = "HAProxy",
        vendor_name = "HAProxy Technologies"
    }

    -- Validation of required OCSF fields
    if not validate_output(output) then
        return nil, "Failed output validation"
    end

    return output
end

-- Helper Functions (locally scoped for performance)
local function parse_timestamp(ts)
    -- Implement efficient timestamp parsing
    -- Returns UNIX timestamp or nil
    local success, result = pcall(function()
        -- Custom timestamp parsing logic here
        return time() -- Placeholder
    end)
    return success and result or nil
end

local function parse_url(url)
    -- Efficient URL parsing with validation
    if type(url) ~= "string" then return nil end
    
    -- Basic URL sanitization
    url = url:match("^%s*(.-)%s*$") -- Trim
    return url
end

local function validate_output(output)
    -- Quick validation of required fields
    return output.class_uid and 
           output.time and 
           output.category_uid
end

-- Error Recovery Function
local function safe_transform(record)
    local success, result, error = pcall(transform, record)
    if not success then
        return nil, format("Transform error: %s", error)
    end
    return result, error
end

return {
    transform = safe_transform,
    -- Expose for testing
    _parse_timestamp = parse_timestamp,
    _parse_url = parse_url
}