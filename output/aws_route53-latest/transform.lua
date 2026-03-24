-- SentinelOne Parser: aws_route53-latest
-- OCSF Class: DNS Activity (4003)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:51:01.656536

-- Pre-compile patterns for performance
local PATTERNS = {
    ip = "^%d+%.%d+%.%d+%.%d+$",
    response_code = "^(NOERROR|NXDOMAIN|SERVFAIL|REFUSED|TIMEOUT)$",
    edge_location = "^[A-Z]{3}%d%d%-P%d$"
}

-- Cache common strings
local STATUS_MAP = {
    NOERROR = 1,
    NXDOMAIN = 2,
    SERVFAIL = 2, 
    REFUSED = 2,
    TIMEOUT = 2
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize output with local variables for performance
    local output = {
        -- Core OCSF fields
        class_uid = 4003,
        class_name = "DNS Activity", 
        category_uid = 4,
        category_name = "Network Activity",
        type_uid = 400306,
        activity_id = 6,
        activity_name = "Traffic",
        severity_id = 1,

        -- Initialize nested tables
        query = {},
        src_endpoint = {},
        dst_endpoint = {},
        observables = {}
    }

    -- Efficient field mapping with validation
    local function safe_copy(src_field, dest_field)
        local value = record[src_field]
        if value and type(value) == "string" then
            -- Remove quotes if present
            value = value:gsub('^"(.*)"$', '%1')
            return value
        end
        return nil
    end

    -- Map timestamp
    output.time = safe_copy("timestamp")
    
    -- Map query fields
    output.query.hostname = safe_copy("query_name")
    output.query.type = safe_copy("query_type")

    -- Map source endpoint
    local client_ip = safe_copy("client_ip")
    if client_ip and client_ip:match(PATTERNS.ip) then
        output.src_endpoint.ip = client_ip
    end

    -- Map edge location
    local edge_loc = safe_copy("edge_location")
    if edge_loc and edge_loc:match(PATTERNS.edge_location) then
        output.src_endpoint.location = {desc = edge_loc}
    end

    -- Map response code and status
    local response_code = safe_copy("response_code")
    if response_code then
        output.rcode = response_code
        output.status_id = STATUS_MAP[response_code] or 2
    end

    -- Map resolver endpoint
    local resolver_id = safe_copy("resolver_id")
    if resolver_id then
        output.dst_endpoint.uid = resolver_id
    end

    -- Generate observables efficiently
    if client_ip and output.query.hostname then
        output.observables = {
            {
                name = "client_ip",
                type = "IP Address", 
                value = client_ip
            },
            {
                name = "query_hostname",
                type = "Hostname",
                value = output.query.hostname
            }
        }
    end

    -- Validate required fields
    if not output.time or not output.query.hostname then
        return nil, "Missing required fields"
    end

    return output
end

-- Error handler wrapper
function safe_transform(record)
    local status, result = pcall(transform, record)
    if not status then
        return nil, "Transform error: " .. tostring(result)
    end
    return result
end