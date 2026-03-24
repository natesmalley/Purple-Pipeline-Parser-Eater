-- SentinelOne Parser: rsa_adaptive-latest 
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:09:34.652982

-- Pre-declare locals for performance
local type = type
local os_time = os.time
local string_format = string.format
local error_msgs = {
    invalid_input = "Invalid input record",
    missing_class = "Invalid class_uid",
    missing_auth = "Missing authentication event data"
}

-- Cache OCSF constants
local OCSF_CONSTANTS = {
    class_uid = 3002,
    class_name = "Authentication",
    category_uid = 3, 
    category_name = "Identity & Access Management",
    activity_id = 1,
    type_uid = 300201
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, error_msgs.invalid_input
    end

    -- Initialize OCSF-compliant output structure with cached constants
    local output = {
        class_uid = OCSF_CONSTANTS.class_uid,
        class_name = OCSF_CONSTANTS.class_name,
        category_uid = OCSF_CONSTANTS.category_uid,
        category_name = OCSF_CONSTANTS.category_name,
        activity_id = OCSF_CONSTANTS.activity_id,
        type_uid = OCSF_CONSTANTS.type_uid,
        metadata = {
            product = {
                name = "RSA Adaptive Authentication",
                vendor_name = "RSA"
            },
            version = "1.0"
        }
    }

    -- Efficient field transformations using local references
    local auth_event = record.authentication_event
    if auth_event then
        output.activity_name = auth_event
        
        -- Add normalized status if available
        if type(auth_event) == "string" then
            output.status = string_format("authentication_%s", auth_event:lower())
        end
    else
        return nil, error_msgs.missing_auth
    end

    -- Add timestamps
    local current_time = os_time() * 1000
    output.time = record.time or current_time
    output.metadata.processed_time = current_time

    -- Validation of required fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, error_msgs.missing_class
    end

    -- Optional enrichment based on RSA specific fields
    if record.risk_score then
        output.risk = {
            score = tonumber(record.risk_score) or 0,
            severity = record.risk_severity or "unknown"
        }
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

-- Performance test helper
local function benchmark(iterations)
    local start = os_time()
    local test_record = {
        authentication_event = "SUCCESS",
        risk_score = "75"
    }
    
    for i=1,iterations do
        safe_transform(test_record)
    end
    
    return os_time() - start
end

-- Test cases
local function run_tests()
    local tests = {
        {
            name = "Valid authentication",
            input = {authentication_event = "SUCCESS"},
            expected = true
        },
        {
            name = "Missing auth event",
            input = {},
            expected = false
        },
        {
            name = "Invalid input",
            input = nil,
            expected = false
        }
    }

    for _, test in ipairs(tests) do
        local result = safe_transform(test.input)
        assert(result ~= nil == test.expected, 
               string_format("Test '%s' failed", test.name))
    end
end