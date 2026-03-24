-- SentinelOne Parser: json_nested_kv_logs-latest 
-- OCSF Class: Generic Log (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:03:58.890877

-- Pre-compile patterns for performance
local timestamp_pattern = "^%d+%.?%d*$"
local identifier_pattern = "^[%w%-_%.]+$"

-- Cache frequently used functions
local type = type
local tonumber = tonumber
local os_time = os.time
local string_match = string.match
local string_format = string.format

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local table
    local output = {
        class_uid = 1001,
        class_name = "Generic Log", 
        category_uid = 1,
        category_name = "System Activity",
        activity_id = 1,
        type_uid = 100101,
        metadata = {},
        time = os_time() * 1000 -- Default timestamp
    }

    -- Optimized timestamp handling
    local time_generated = record["time-generated"]
    if time_generated then
        if type(time_generated) == "number" then
            output.timestamp = time_generated
        elseif type(time_generated) == "string" and string_match(time_generated, timestamp_pattern) then
            output.timestamp = tonumber(time_generated)
        end
    end

    -- Optimized identifier handling
    local identifier = record.identifier
    if identifier and type(identifier) == "string" then
        if string_match(identifier, identifier_pattern) then
            output.metadata.key = identifier
        end
    end

    -- Process nested key-value pairs efficiently
    local nested = {}
    for k, v in pairs(record) do
        if type(k) == "string" and type(v) ~= "table" then
            -- Convert to dotted notation
            local clean_key = string_match(k, "^[%w%-_%.]+$")
            if clean_key then
                nested[clean_key] = v
            end
        end
    end
    output.metadata.nested_fields = nested

    -- Validation checks
    if not output.timestamp then
        output.timestamp = output.time -- Use default if no valid timestamp
    end

    -- Error checking for required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    return output
end

-- Error recovery function
local function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end

-- Cached utility functions for performance
local function validate_timestamp(ts)
    if type(ts) == "number" then return ts end
    if type(ts) == "string" then
        local num = tonumber(ts)
        return num and num > 0 and num or nil
    end
    return nil
end

local function clean_string(str)
    if type(str) ~= "string" then return nil end
    return string_match(str, "^[%w%-_%.%s]+$")
end

-- Test cases with expected results
local test_cases = {
    {
        input = {
            ["time-generated"] = "1634567890",
            identifier = "test_id",
            field1 = "value1"
        },
        expected_class_uid = 1001
    },
    {
        input = nil,
        expected_error = "Invalid input record"
    },
    {
        input = {},
        expected_class_uid = 1001
    }
}