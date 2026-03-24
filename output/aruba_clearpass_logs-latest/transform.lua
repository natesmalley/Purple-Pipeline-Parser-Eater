-- SentinelOne Parser: aruba_clearpass_logs-latest 
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-16T14:58:16.851006

-- Pre-compile patterns for performance
local TIMESTAMP_PATTERN = "^(%d%d%d%d%-%d%d%-%d%d %d%d:%d%d:%d%d),%d+"
local IPV4_PATTERN = "(%d+%.%d+%.%d+%.%d+)"

-- Utility functions
local function parse_timestamp(ts)
    if not ts then return nil end
    local y,m,d,h,min,s = ts:match("(%d+)-(%d+)-(%d+) (%d+):(%d+):(%d+)")
    if not y then return nil end
    return os.time({year=y, month=m, day=d, hour=h, min=min, sec=s}) * 1000
end

local function parse_details(details)
    if not details then return {} end
    local result = {}
    for k,v in details:gmatch("([^,=]+)=([^,]+)") do
        result[k:trim()] = v:trim()
    end
    return result
end

function transform(record)
    -- Input validation
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize output with required OCSF fields
    local output = {
        class_uid = 3002,
        class_name = "Authentication",
        category_uid = 3, 
        category_name = "Identity & Access Management",
        metadata = {
            product = {
                name = "ClearPass",
                vendor = "Aruba Networks"
            },
            version = "1.0"
        }
    }

    -- Extract and validate timestamp
    local timestamp = record.timestamp
    if timestamp then
        local parsed_time = parse_timestamp(timestamp)
        if parsed_time then
            output.time = parsed_time
        else
            output.time = os.time() * 1000
        end
    end

    -- Extract and validate IP
    local src_ip = record.ip
    if src_ip and src_ip:match(IPV4_PATTERN) then
        output.src = {ip = src_ip}
    end

    -- Parse details into event parameters
    if record.details then
        local params = parse_details(record.details)
        if next(params) then
            output.event = {params = params}
        end
    end

    -- Add log type classification
    local log_type = record.log_number and record.log_number:match("^(%w+)")
    if log_type then
        output.type_name = log_type
        output.type_uid = 300201 -- Default Authentication type
    end

    -- Validation and enrichment
    if not output.time then
        output.time = os.time() * 1000
    end

    -- Add severity if available
    if record.field1 and record.field1:match("[INFO|WARN|ERROR]") then
        output.severity = record.field1
    end

    return output
end

-- Error handling wrapper
function safe_transform(record)
    local status, result = pcall(transform, record)
    if status then
        return result
    else
        return nil, string.format("Transform error: %s", result)
    end
end