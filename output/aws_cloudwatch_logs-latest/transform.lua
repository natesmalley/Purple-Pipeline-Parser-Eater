-- SentinelOne Parser: aws_cloudwatch_logs-latest 
-- OCSF Class: Network Activity (2001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-16T14:58:36.437186

-- Pre-declare locals for performance
local type = type
local pairs = pairs
local os_time = os.time
local string_format = string.format
local table_insert = table.insert

-- Validation patterns
local IP_PATTERN = "^%d+%.%d+%.%d+%.%d+$"
local UUID_PATTERN = "^%x%x%x%x%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%x%x%x%x%x%x%x%x$"

-- Initialize static OCSF structure once
local OCSF_BASE = {
    class_uid = 2001,
    class_name = "Network Activity", 
    category_uid = 2,
    category_name = "Network Activity",
    activity_id = 1,
    type_uid = 200101,
    metadata = {
        version = "1.0.0",
        product = {
            name = "AWS CloudWatch",
            vendor_name = "AWS"
        }
    }
}

local function validate_ip(ip)
    if not ip or type(ip) ~= "string" then return false end
    return ip:match(IP_PATTERN) ~= nil
end

local function validate_uuid(uuid)
    if not uuid or type(uuid) ~= "string" then return false end
    return uuid:match(UUID_PATTERN) ~= nil
end

local function deep_copy(orig)
    local orig_type = type(orig)
    local copy
    if orig_type == 'table' then
        copy = {}
        for orig_key, orig_value in pairs(orig) do
            copy[orig_key] = deep_copy(orig_value)
        end
    else
        copy = orig
    end
    return copy
end

function transform(record)
    -- Input validation with detailed error
    if not record then
        return nil, "Record is nil"
    end
    if type(record) ~= "table" then
        return nil, string_format("Expected table, got %s", type(record))
    end

    -- Create new output table with OCSF base structure
    local output = deep_copy(OCSF_BASE)
    
    -- Initialize nested structures
    output.src_endpoint = {}
    output.dst_endpoint = {}
    output.cloud = {account = {}}

    -- Optimized field transformations with validation
    if record.srcaddr then
        if validate_ip(record.srcaddr) then
            output.src_endpoint.ip = record.srcaddr
        else
            return nil, string_format("Invalid source IP: %s", record.srcaddr)
        end
    end

    if record.dstaddr then
        if validate_ip(record.dstaddr) then
            output.dst_endpoint.ip = record.dstaddr
        else
            return nil, string_format("Invalid destination IP: %s", record.dstaddr)
        end
    end

    -- Handle account-id with hyphen syntax
    local account_id = record["account-id"] or record.account_id
    if account_id then
        output.cloud.account.uid = account_id
    end

    -- Add additional VPC flow log fields if present
    if record.protocol then
        output.network = {
            protocol = tonumber(record.protocol),
            bytes = tonumber(record.bytes) or 0,
            packets = tonumber(record.packets) or 0
        }
    end

    -- Handle timestamps
    if record.start then
        output.time_start = tonumber(record.start) * 1000
    end
    if record.end then
        output.time_end = tonumber(record.end) * 1000
    end
    
    -- Set default timestamp if none provided
    if not output.time then
        output.time = os_time() * 1000
    end

    -- Validate required OCSF fields
    if not output.src_endpoint.ip and not output.dst_endpoint.ip then
        return nil, "Missing both source and destination IPs"
    end

    return output
end

-- Error handling wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end