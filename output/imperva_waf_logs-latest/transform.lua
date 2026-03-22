-- SentinelOne Parser: imperva_waf_logs-latest 
-- OCSF Class: Web Application Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:02:14.806667

-- Pre-compile patterns for performance
local IP_PATTERN = "^%d+%.%d+%.%d+%.%d+$"
local TIMESTAMP_PATTERN = "^%d+$"

-- Local helper functions for validation
local function validate_ip(ip)
    if not ip then return false end
    return string.match(ip, IP_PATTERN) ~= nil
end

local function validate_timestamp(ts)
    if not ts then return false end
    return string.match(ts, TIMESTAMP_PATTERN) ~= nil
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize output structure with local variables
    local output = {
        class_uid = 1001,
        class_name = "Web Application Activity",
        category_uid = 1, 
        category_name = "Application Activity",
        activity_id = 1,
        type_uid = 100101,
        metadata = {
            product = {
                name = "Imperva WAF",
                vendor_name = "Imperva"
            }
        },
        src_endpoint = {},
        dst_endpoint = {}
    }

    -- Efficient field transformations using local vars
    local src_ip = record.unmapped and record.unmapped.src
    local dst_ip = record.unmapped and record.unmapped.dst
    local event_type = record.event and record.event.type
    local timestamp = record.timestamp

    -- IP Address Transformations with validation
    if src_ip and validate_ip(src_ip) then
        output.src_endpoint.ip = src_ip
    end

    if dst_ip and validate_ip(dst_ip) then
        output.dst_endpoint.ip = dst_ip
    end

    -- Port number transformations
    local src_port = record.unmapped and record.unmapped.spt
    local dst_port = record.unmapped and record.unmapped.dpt
    
    if src_port and tonumber(src_port) then
        output.src_endpoint.port = tonumber(src_port)
    end
    
    if dst_port and tonumber(dst_port) then
        output.dst_endpoint.port = tonumber(dst_port)
    end

    -- Event type mapping
    if event_type then
        output.activity_name = event_type
    end

    -- Timestamp handling with validation
    if timestamp and validate_timestamp(timestamp) then
        output.time = tonumber(timestamp)
    else
        output.time = os.time() * 1000 -- Fallback to current time in milliseconds
    end

    -- Additional WAF-specific fields
    if record.unmapped then
        -- Customer/Account mapping
        if record.unmapped.Customer then
            output.account = {
                name = record.unmapped.Customer
            }
        end

        -- Application details
        if record.unmapped.requestClientApplication then
            output.user_agent = record.unmapped.requestClientApplication
        end
    end

    -- Validation of required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    -- Add severity if present
    if record.severity then
        output.severity = tonumber(record.severity) or 0
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