-- SentinelOne Parser: meraki_logs-latest
-- OCSF Class: Network Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:05:49.884176

-- Pre-declare locals for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_format = string.format
local error_msgs = {
    invalid_input = "Invalid input record",
    missing_required = "Missing required fields",
    invalid_class = "Invalid class_uid"
}

-- Initialize static OCSF fields once
local OCSF_STATIC = {
    class_uid = 1001,
    class_name = "Network Activity", 
    category_uid = 1,
    category_name = "Network Activity",
    activity_id = 1,
    type_uid = 100101
}

function transform(record)
    -- Fast input validation
    if not record or type(record) ~= "table" then
        return nil, error_msgs.invalid_input
    end

    -- Initialize output with static fields using efficient table copy
    local output = {
        class_uid = OCSF_STATIC.class_uid,
        class_name = OCSF_STATIC.class_name,
        category_uid = OCSF_STATIC.category_uid,
        category_name = OCSF_STATIC.category_name,
        activity_id = OCSF_STATIC.activity_id,
        type_uid = OCSF_STATIC.type_uid,
        device = {} -- Pre-initialize nested table
    }

    -- Optimized field transformations with type checking
    local timestamp = record.timestamp
    if timestamp then
        local ts_num = tonumber(timestamp)
        if ts_num then
            output.time = ts_num
        end
    end

    -- Direct field copies with validation
    local hostname = record.hostname
    if hostname and type(hostname) == "string" then
        output.device.hostname = hostname
    end

    local op = record.op
    if op and type(op) == "string" then
        output.activity_name = op
    end

    -- Ensure required fields
    if not output.time then
        output.time = os_time() * 1000 -- Convert to milliseconds
    end

    -- Final validation
    if not output.class_uid or output.class_uid == 0 then
        return nil, error_msgs.invalid_class
    end

    -- Add metadata for debugging if enabled
    if record._debug then
        output._metadata = {
            parser_version = "1.0.0",
            processed_at = os_time()
        }
    end

    return output
end

-- Error recovery function
local function recover_from_error(err, record)
    if not record then return nil end
    
    -- Attempt basic recovery
    local recovered = {
        class_uid = OCSF_STATIC.class_uid,
        time = os_time() * 1000,
        error = string_format("Recovery from: %s", err)
    }
    return recovered
end

-- Validation helper
local function validate_record(record)
    if not record then return false end
    if type(record) ~= "table" then return false end
    return true
end