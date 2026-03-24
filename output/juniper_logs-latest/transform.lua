-- SentinelOne Parser: juniper_logs-latest
-- OCSF Class: Network Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:03:58.886537

-- Pre-compile patterns for performance
local timestamp_pattern = "^(%w+)%s+(%d+)%s+(%d+):(%d+):(%d+)"
local ip_pattern = "^%d+%.%d+%.%d+%.%d+$"

-- Local helper functions for performance
local function validate_ip(ip)
    if not ip then return false end
    return ip:match(ip_pattern) ~= nil
end

local function parse_timestamp(ts)
    if not ts then return nil end
    local month, day, hour, min, sec = ts:match(timestamp_pattern)
    if not month then return nil end
    -- Convert to UNIX timestamp (simplified)
    return os.time({
        year = os.date("*t").year,
        month = month,
        day = tonumber(day),
        hour = tonumber(hour),
        min = tonumber(min),
        sec = tonumber(sec)
    }) * 1000
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local table
    local output = {
        class_uid = 1001,
        class_name = "Network Activity",
        category_uid = 1,
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = 100101,
        metadata = {
            version = "1.0.0",
            product = {
                name = "Juniper Networks Firewall",
                vendor = "Juniper Networks"
            }
        },
        src_endpoint = {},
        device = {}
    }

    -- Efficient timestamp handling
    local timestamp = record.timestamp
    if timestamp then
        output.time = parse_timestamp(timestamp)
    else
        output.time = os.time() * 1000
    end

    -- Optimized IP address handling
    if record.src and record.src.ip and record.src.ip.address then
        local src_ip = record.src.ip.address
        if validate_ip(src_ip) then
            output.src_endpoint.ip = src_ip
        end
    end

    -- Efficient hostname handling
    if record.endpoint and record.endpoint.name then
        local hostname = record.endpoint.name
        if type(hostname) == "string" and #hostname > 0 then
            output.device.hostname = hostname
        end
    end

    -- Handle original time if present
    if record.metadata and record.metadata.original_time then
        output.metadata.original_time = record.metadata.original_time
    end

    -- Validation of required OCSF fields
    if not output.time then
        return nil, "Missing or invalid timestamp"
    end

    if not output.src_endpoint.ip and not output.device.hostname then
        return nil, "Missing required source identification"
    end

    -- Add observability metadata
    output.metadata.processing = {
        timestamp = os.time() * 1000,
        parser_version = "1.0.0"
    }

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