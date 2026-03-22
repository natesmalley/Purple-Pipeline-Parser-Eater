-- SentinelOne Parser: generic_access_logs-latest 
-- OCSF Class: HTTP Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:00:29.823709

-- Pre-compile patterns for performance
local URI_PATTERN = "^([^?#]*)"
local STATUS_PATTERN = "^%d%d%d$"

-- Cache frequently used functions
local tonumber = tonumber
local type = type
local format = string.format
local match = string.match

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with nested tables
    local output = {
        class_uid = 1001,
        class_name = "HTTP Activity", 
        category_uid = 1,
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = 100101,
        src_endpoint = {},
        user = {},
        http_request = {},
        http_response = {}
    }

    -- IP Address transformation with validation
    if record.ip then
        local ip = record.ip
        if type(ip) == "string" and ip:match("^%d+%.%d+%.%d+%.%d+$") then
            output.src_endpoint.ip = ip
        end
    end

    -- User transformation with sanitization
    if record.user and record.user ~= "-" then
        output.user.name = record.user
    end

    -- HTTP Method transformation with validation
    if record.method then
        local method = record.method:upper()
        if method:match("^[A-Z]+$") then
            output.http_request.method = method
        end
    end

    -- URI transformation with parsing
    if record.uri then
        local base_uri = match(record.uri, URI_PATTERN)
        if base_uri then
            output.http_request.url = base_uri
        end
    end

    -- Status code transformation with type casting
    if record.status then
        local status = tonumber(record.status)
        if status and status >= 100 and status < 600 then
            output.http_response.status_code = status
        end
    end

    -- Optional fields processing
    if record.bytes then
        local bytes = tonumber(record.bytes)
        if bytes then
            output.http_response.bytes = bytes
        end
    end

    if record.referrer and record.referrer ~= "-" then
        output.http_request.referrer = record.referrer
    end

    if record.agent and record.agent ~= "-" then
        output.http_request.user_agent = record.agent
    end

    -- Timestamp handling
    if record.timestamp then
        -- Assuming timestamp is in standard format
        output.time = record.timestamp
    else
        output.time = os.time() * 1000
    end

    -- Final validation of required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    -- Add metadata
    output.metadata = {
        version = "1.0.0",
        product = {
            name = "Generic Web Server",
            vendor_name = "Generic"
        }
    }

    return output
end

-- Error wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, format("Transform error: %s", result)
    end
    return result
end