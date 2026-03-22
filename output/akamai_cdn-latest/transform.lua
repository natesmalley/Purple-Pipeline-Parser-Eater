-- SentinelOne Parser: akamai_cdn-latest
-- OCSF Class: HTTP Activity (4002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-16T14:56:31.549553

-- Pre-compile patterns for performance
local patterns = {
    ip = "^%d+%.%d+%.%d+%.%d+$",
    status = "^%d%d%d$",
    cache = "^(HIT|MISS|PASS)$"
}

-- Local helper functions for performance
local function validate_ip(ip)
    if not ip then return nil end
    return string.match(ip, patterns.ip) and ip or nil
end

local function validate_status(code)
    if not code then return nil end
    local num = tonumber(code)
    return (num and num >= 100 and num < 600) and num or nil
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize output structure with local references
    local output = {
        -- OCSF required fields
        class_uid = 4002,
        class_name = "HTTP Activity", 
        category_uid = 4,
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = 400201,
        
        -- Initialize nested structures
        src_endpoint = {},
        dst_endpoint = {},
        http_request = {},
        http_response = {},
        enrichments = {},
        metadata = {},
        observables = {}
    }

    -- Timestamp handling with validation
    local timestamp = record.timestamp
    if timestamp then
        output.time = timestamp
    else
        output.time = os.time() * 1000
    end

    -- IP address handling with validation
    local client_ip = validate_ip(record.client_ip)
    if client_ip then
        output.src_endpoint.ip = client_ip
    end

    local edge_ip = validate_ip(record.edge_ip)
    if edge_ip then
        output.dst_endpoint.ip = edge_ip
    end

    -- HTTP request fields
    if record.host then
        output.http_request.hostname = record.host
    end
    if record.method then
        output.http_request.http_method = record.method
    end
    if record.path then
        output.http_request.url = {path = record.path}
    end

    -- HTTP response fields
    local status = validate_status(record.status_code)
    if status then
        output.http_response.code = status
        -- Set status_id based on status code range
        output.status_id = status >= 200 and status < 300 and 1 or 2
    end

    -- Handle numeric fields
    if record.bytes then
        output.http_response.length = tonumber(record.bytes)
    end
    if record.response_time_ms then
        output.response_time = tonumber(record.response_time_ms)
    end

    -- Cache status handling with validation
    if record.cache_status and string.match(record.cache_status, patterns.cache) then
        output.enrichments.cache_status = record.cache_status
    end

    -- Location data
    if record.country then
        output.src_endpoint.location = output.src_endpoint.location or {}
        output.src_endpoint.location.country = record.country
    end
    if record.city then
        output.src_endpoint.location = output.src_endpoint.location or {}
        output.src_endpoint.location.city = record.city
    end

    -- Metadata fields
    if record.request_id then
        output.metadata.correlation_uid = record.request_id
    end
    if record.stream_id then
        output.metadata.log_name = record.stream_id
    end

    -- Generate observables
    if client_ip and record.host then
        output.observables = {
            {name = "src_ip", type = "IP Address", value = client_ip},
            {name = "hostname", type = "Hostname", value = record.host}
        }
    end

    return output
end