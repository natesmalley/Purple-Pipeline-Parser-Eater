-- SentinelOne Parser: singularityidentity_singularityidentity_logs-latest 
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T11:12:37.672063

-- Pre-declare locals for performance
local type = type
local os_time = os.time
local string_format = string.format
local table_insert = table.insert

-- Validation constants
local REQUIRED_FIELDS = {
    "raw_event"
}

-- Error messages
local ERROR_MESSAGES = {
    invalid_input = "Invalid input record",
    missing_required = "Missing required field: %s",
    invalid_class = "Invalid class_uid"
}

-- Optimized field validation
local function validate_record(record)
    if not record or type(record) ~= "table" then
        return false, ERROR_MESSAGES.invalid_input
    end
    
    for _, field in ipairs(REQUIRED_FIELDS) do
        if not record[field] then
            return false, string_format(ERROR_MESSAGES.missing_required, field)
        end
    end
    
    return true
end

function transform(record)
    -- Fast input validation
    local is_valid, error_msg = validate_record(record)
    if not is_valid then
        return nil, error_msg
    end

    -- Initialize output with static OCSF fields
    local output = {
        class_uid = 3002,
        class_name = "Authentication",
        category_uid = 3,
        category_name = "Identity & Access Management",
        activity_id = 1,
        type_uid = 300201,
        metadata = {
            version = "1.0.0",
            product = {
                name = "SingularityIdentity",
                vendor = "SentinelOne"
            }
        }
    }

    -- Optimized field mappings
    local raw_event = record.raw_event
    if raw_event then
        output.event_raw = raw_event
        
        -- Extract additional fields if available
        if type(raw_event) == "table" then
            -- Add conditional field mappings here
            output.time = raw_event.timestamp or (os_time() * 1000)
            output.severity = raw_event.severity
            output.status = raw_event.status
        end
    end

    -- Set default timestamp if not present
    if not output.time then
        output.time = os_time() * 1000
    end

    -- Final validation
    if not output.class_uid or output.class_uid == 0 then
        return nil, ERROR_MESSAGES.invalid_class
    end

    return output
end

-- Error recovery function
local function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, "Transform error: " .. tostring(result)
    end
    return result
end

-- Test cases
local function run_tests()
    local test_cases = {
        {
            input = {raw_event = {timestamp = 1634567890000}},
            expected = true
        },
        {
            input = nil,
            expected = false
        },
        {
            input = {},
            expected = false
        }
    }

    local results = {}
    for i, test in ipairs(test_cases) do
        local output, error = safe_transform(test.input)
        results[i] = {
            passed = (output ~= nil) == test.expected,
            error = error
        }
    end
    return results
end

return {
    transform = safe_transform,
    run_tests = run_tests
}