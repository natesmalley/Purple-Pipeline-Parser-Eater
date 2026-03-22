-- SentinelOne Parser: fortinet_logs-latest 
-- OCSF Class: Network Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:59:57.621340

-- Pre-compile patterns for performance
local patterns = {
    ip = "^%d+%.%d+%.%d+%.%d+$",
    port = "^%d+$",
    timestamp = "^%d+$"
}

-- Cached references for better performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_match = string.match
local string_format = string.format

-- Validation helper functions
local function validate_ip(ip)
    if not ip then return false end
    return string_match(ip, patterns.ip) ~= nil
end

local function validate_timestamp(ts)
    if not ts then return false end
    local num = tonumber(ts)
    return num and num > 0 and num < 32503680000 -- Valid through year 3000
end

function transform(record)
    -- Input validation with detailed error reporting
    if not record then
        return nil, "Missing input record"
    end
    if type(record) ~= "table" then
        return nil, string_format("Invalid input type: %s", type(record))
    end

    -- Initialize OCSF-compliant output structure with local references
    local output = {
        metadata = {
            version = "1.0.0",
            class_uid = 1001,
            class_name = "Network Activity",
            category_uid = 1, 
            category_name = "Network & Security"
        },
        network_activity = {},
        device = {},
        dst = {
            ip = {}
        },
        policy = {}
    }

    -- Optimized field transformations using local tables
    local network_activity = output.network_activity
    local device = output.device
    local dst = output.dst
    local policy = output.policy

    -- Transform action with validation
    if record.action then
        network_activity.action = record.action
    end

    -- Transform destination IP with validation
    if record.dstip and validate_ip(record.dstip) then
        dst.ip.address = record.dstip
    end

    -- Transform event time with validation
    if record.eventtime and validate_timestamp(record.eventtime) then
        network_activity.start_time = tonumber(record.eventtime)
    else
        network_activity.start_time = os_time() * 1000
    end

    -- Additional field mappings with validation
    if record.devid then device.uid = record.devid end
    if record.devname then device.name = record.devname end
    if record.dstintf then device.dst_interface_uid = record.dstintf end
    if record.policyid then policy.name = record.policyid end
    if record.policytype then policy.type = record.policytype end
    if record.poluuid then policy.uid = record.poluuid end

    -- Validate required OCSF fields
    if not output.metadata.class_uid then
        return nil, "Missing required class_uid"
    end

    -- Add processing metadata
    output.metadata.processed_time = os_time() * 1000
    output.metadata.parser_version = "1.0.0"

    return output
end

-- Error handler wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end