-- SentinelOne Parser: iis_w3c-latest 
-- OCSF Class: HTTP Activity (4002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:01:45.712004

-- Pre-declare locals for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_format = string.format
local error_msgs = {
    invalid_input = "Invalid input record",
    missing_required = "Missing required fields",
    invalid_timestamp = "Invalid timestamp format"
}

-- Cached OCSF constants
local OCSF_CONSTANTS = {
    class_uid = 4002,
    class_name = "HTTP Activity", 
    category_uid = 4,
    category_name = "Network Activity",
    activity_id = 6,
    activity_name = "Traffic",
    type_uid = 400206,
    type_name = "HTTP Activity: Traffic"
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, error_msgs.invalid_input
    end

    -- Initialize output with cached constants
    local output = {
        -- OCSF Classification
        class_uid = OCSF_CONSTANTS.class_uid,
        class_name = OCSF_CONSTANTS.class_name,
        category_uid = OCSF_CONSTANTS.category_uid,
        category_name = OCSF_CONSTANTS.category_name,
        activity_id = OCSF_CONSTANTS.activity_id,
        activity_name = OCSF_CONSTANTS.activity_name,
        type_uid = OCSF_CONSTANTS.type_uid,
        type_name = OCSF_CONSTANTS.type_name,
        
        -- Initialize nested structures
        src_endpoint = {},
        dst_endpoint = {},
        http_request = {
            url = {}
        },
        http_response = {},
        actor = {
            user = {}
        }
    }

    -- Timestamp handling with validation
    if record.unmapped and record.unmapped.timestamp then
        local ts = tonumber(record.unmapped.timestamp)
        if ts then
            output.time = ts
        else
            return nil, error_msgs.invalid_timestamp
        end
    else
        output.time = os_time() * 1000
    end

    -- Efficient field mappings using local references
    local unmapped = record.unmapped
    if unmapped then
        -- Source endpoint
        output.src_endpoint.ip = unmapped.client_ip
        
        -- Destination endpoint
        output.dst_endpoint.ip = unmapped.server_ip
        output.dst_endpoint.port = tonumber(unmapped.server_port)
        output.dst_endpoint.hostname = unmapped.sitename
        output.dst_endpoint.name = unmapped.computername
        
        -- HTTP Request
        output.http_request.http_method = unmapped.method
        output.http_request.url.path = unmapped.uri_stem
        output.http_request.url.query_string = unmapped.uri_query
        output.http_request.length = tonumber(unmapped.bytes_received)
        output.http_request.user_agent = unmapped.user_agent
        
        -- HTTP Response
        output.http_response.code = tonumber(unmapped.status_code)
        output.http_response.length = tonumber(unmapped.bytes_sent)
        
        -- Actor
        output.actor.user.name = unmapped.username
    end

    -- Validation of required fields
    if not output.src_endpoint.ip or not output.http_request.http_method then
        return nil, error_msgs.missing_required
    end

    return output
end

-- Error handling wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end