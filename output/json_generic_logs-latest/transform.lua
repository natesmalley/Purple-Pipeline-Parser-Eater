-- SentinelOne Parser: json_generic_logs-latest 
-- OCSF Class: Generic (1000)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:03:57.876633

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
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local reference
    local output = {
        -- Required OCSF fields
        class_uid = 1000,
        class_name = "Generic",
        category_uid = 1, 
        category_name = "Base",
        activity_id = 1,
        type_uid = 100001,
        metadata = {
            version = "1.0.0",
            product = {
                name = "Generic JSON Parser",
                vendor_name = "Observo.ai"
            }
        }
    }

    -- Performance-optimized field transformations
    local dynamic_fields = {}
    
    -- Process all fields in record
    for key, value in pairs(record) do
        -- Skip nil values
        if value ~= nil then
            -- Handle nested tables
            if type(value) == "table" then
                dynamic_fields[key] = value
            -- Handle scalar values    
            else
                -- Use string.format for string concatenation
                local formatted_value = type(value) == "string" and 
                    string_format("%s", value) or value
                dynamic_fields[key] = formatted_value
            end
        end
    end

    -- Only set dynamic if we have fields
    if next(dynamic_fields) then
        output.dynamic = dynamic_fields
    end

    -- Add observability fields
    output.observability = {
        parser_id = "json_generic_logs-latest",
        ingestion_time = os_time() * 1000
    }

    -- Validation and cleanup
    if not validate_number(output.class_uid) then
        return nil, "Invalid class_uid"
    end

    -- Add timestamp if not present
    if not output.time then
        output.time = os_time() * 1000
    end

    -- Final validation of required fields
    local required_fields = {"class_uid", "class_name", "category_uid"}
    for _, field in ipairs(required_fields) do
        if not output[field] then
            return nil, string_format("Missing required field: %s", field)
        end
    end

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

-- Built-in test cases
local function run_tests()
    local test_cases = {
        {
            input = {field1 = "value1", field2 = 123},
            expected = true
        },
        {
            input = nil,
            expected = false
        },
        {
            input = {},
            expected = true
        }
    }

    for i, test in ipairs(test_cases) do
        local result = safe_transform(test.input)
        local passed = (result ~= nil) == test.expected
        if not passed then
            print(string_format("Test %d failed", i))
        end
    end
end