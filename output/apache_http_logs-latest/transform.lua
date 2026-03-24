-- SentinelOne Parser: apache_http_logs-latest
-- OCSF Class: HTTP Activity (6001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-16T14:57:55.600065

-- Pre-compile patterns for performance
local IP_PATTERN = "^%d+%.%d+%.%d+%.%d+$"
local TIMESTAMP_PATTERN = "^%d%d/%w+/%d%d%d%d:%d%d:%d%d:%d%d%s[+-]%d+"

-- HTTP method mapping table for O(1) lookups
local HTTP_METHOD_MAP = {
    DELETE = 2,
    GET = 3,
    POST = 6,
    PUT = 7,
    HEAD = 8,
    OPTIONS = 9
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local table
    local output = {
        class_uid = 6001,
        class_name = "HTTP Activity",
        category_uid = 6,
        category_name = "Network Activity",
        type_uid = 600101,
        metadata = {
            version = "1.0.0",
            product = {
                name = "Apache HTTP Server",
                vendor = "Apache"
            }
        },
        src_endpoint = {},
        http_request = {},
        actor = {
            user = {}
        }
    }

    -- Efficient field transformations using local references
    local src_ip = record.src and record.src.ip and record.src.ip.address
    if src_ip and string.match(src_ip, IP_PATTERN) then
        output.src_endpoint.ip = src_ip
    end

    -- Copy user info with validation
    local username = record.actor and record.actor.user and record.actor.user.name
    if username and type(username) == "string" then
        output.actor.user.name = username
    end

    -- Map HTTP method with activity ID
    local method = record.http_request and record.http_request.activity_name
    if method then
        output.http_request.method = method
        output.activity_id = HTTP_METHOD_MAP[method] or 1
    end

    -- Handle HTTP response data
    local response = record.http_response or {}
    if response.code then
        output.http_response = {
            status_code = tonumber(response.code),
            body_length = tonumber(response.body_length) or 0
        }
    end

    -- Process timestamp if present
    local ts = record.timestamp
    if ts and string.match(ts, TIMESTAMP_PATTERN) then
        -- Convert Apache timestamp to UNIX milliseconds
        local pattern = "(%d+)/(%w+)/(%d+):(%d+):(%d+):(%d+)"
        local day, month, year, hour, min, sec = string.match(ts, pattern)
        if day then
            output.time = os.time({
                year = tonumber(year),
                month = month,
                day = tonumber(day),
                hour = tonumber(hour),
                min = tonumber(min),
                sec = tonumber(sec)
            }) * 1000
        end
    else
        output.time = os.time() * 1000
    end

    -- Final validation
    if not output.src_endpoint.ip then
        return nil, "Missing required field: src_endpoint.ip"
    end

    return output
end

-- Error handling wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string.format("Transform error: %s", result)
    end
    return result
end