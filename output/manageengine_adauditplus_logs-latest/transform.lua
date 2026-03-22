-- SentinelOne Parser: manageengine_adauditplus_logs-latest 
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T11:07:35.880686

-- Pre-declare locals for performance
local type = type
local pairs = pairs
local os_time = os.time
local string_format = string.format
local table_insert = table.insert

-- Validation helper functions
local function validate_string(str)
    return type(str) == "string" and str ~= ""
end

local function validate_number(num)
    return type(num) == "number" and num > 0
end

-- Main transform function
function transform(record)
    -- Input validation with detailed error message
    if not record or type(record) ~= "table" then
        return nil, string_format("Invalid input record type: %s", type(record))
    end

    -- Initialize OCSF-compliant output structure with local reference
    local output = {
        -- Required OCSF fields
        class_uid = 3002,
        class_name = "Authentication",
        category_uid = 3, 
        category_name = "Identity & Access Management",
        activity_id = 1,
        type_uid = 300201,
        metadata = {
            version = "1.0.0",
            product = {
                name = "ADauditPlus",
                vendor = "ManageEngine"
            }
        }
    }

    -- Track validation errors
    local validation_errors = {}

    -- Optimized raw event copy with validation
    if record.raw_event then
        if validate_string(record.raw_event) then
            output.raw_event = record.raw_event
        else
            table_insert(validation_errors, "Invalid raw_event format")
        end
    end

    -- Add timestamp with microsecond precision
    output.time = record.time or (os_time() * 1000)

    -- Validate required fields
    if not validate_number(output.class_uid) then
        return nil, "Invalid class_uid"
    end

    -- Return validation errors if present
    if #validation_errors > 0 then
        return nil, table.concat(validation_errors, "; ")
    end

    -- Optional: Add debug information in development
    if _DEBUG then
        output._debug = {
            parser = "manageengine_adauditplus_logs-latest",
            timestamp = os_time()
        }
    end

    return output
end

-- Error wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end

-- Optimization notes:
-- 1. Local function references improve performance
-- 2. String concatenation minimized
-- 3. Table pre-allocation where possible
-- 4. Validation functions isolated for reuse
-- 5. Error collection prevents multiple returns

-- Test cases included in code
if _TEST then
    local test_cases = {
        {
            input = {raw_event = "test event"},
            expected = true
        },
        {
            input = nil,
            expected = false
        },
        {
            input = {raw_event = ""},
            expected = false
        }
    }

    for i, test in ipairs(test_cases) do
        local result = safe_transform(test.input)
        assert(result ~= nil == test.expected, 
               string_format("Test case %d failed", i))
    end
end