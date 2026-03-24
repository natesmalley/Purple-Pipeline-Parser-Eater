--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: pingone_mfa-latest
  Generated: 2025-10-13T12:50:45.188396
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: pingone_mfa-latest
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:29:48.225589

-- Lookup tables for better performance
local STATUS_MAP = {
    SUCCESS = {id = 1, name = "Success"},
    FAILURE = {id = 2, name = "Failure"}
}

local ACTIVITY_MAP = {
    ["MFA.AUTHENTICATE"] = {id = 1, name = "Logon"},
    ["MFA.ENROLL"] = {id = 99, name = "Other"}
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize local variables for performance
    local action_type = record.action and record.action.type
    local result_status = record.result and record.result.status
    local source_ip = record.source and record.source.ip
    local user = record.user

    -- Initialize OCSF-compliant output structure
    local output = {
        -- Static OCSF classification
        class_uid = 3002,
        class_name = "Authentication",
        category_uid = 3, 
        category_name = "Identity & Access Management",
        type_uid = 300201,
        severity_id = 1,
        severity = "Informational",

        -- Product metadata
        metadata = {
            product = {
                vendor_name = "Ping Identity",
                name = "PingOne MFA",
                category = "security"
            }
        }
    }

    -- Timestamp handling with validation
    if record.timestamp then
        output.timestamp = record.timestamp
    elseif record.recordedAt then
        output.timestamp = record.recordedAt
    else
        output.timestamp = os.time() * 1000
    end

    -- Activity mapping with error handling
    if action_type then
        local activity = ACTIVITY_MAP[action_type]
        if activity then
            output.activity_id = activity.id
            output.activity_name = activity.name
        end
    end

    -- Status mapping
    if result_status then
        local status = STATUS_MAP[result_status]
        if status then
            output.status_id = status.id
            output.status = status.name
            output.status_detail = result_status
        end
    end

    -- User information handling
    if user then
        output.user = {
            email_addr = user,
            name = user
        }
    end

    -- Source endpoint handling
    if source_ip then
        output.src_endpoint = {
            ip = source_ip
        }
    end

    -- Optional fields with null checks
    if record.factor then output.mfa_factors = record.factor end
    if record.sessionId then output.session = {uid = record.sessionId} end
    if record.description then output.message = record.description end

    -- Validation of required OCSF fields
    if not output.activity_name or output.activity_name == "" then
        return nil, "Missing required activity_name"
    end

    if not output.status then
        output.status_id = 1
        output.status = "Success"
    end

    return output
end

-- Performance optimizations:
-- 1. Lookup tables for constant mappings
-- 2. Local variables for frequently accessed values
-- 3. Null checks before table access
-- 4. Minimal string operations
-- 5. Single-pass field population
-- 6. Early validation and returns

-- Test function for validation
function test()
    local test_cases = {
        {
            input = {
                action = {type = "MFA.AUTHENTICATE"},
                result = {status = "SUCCESS"},
                user = "user@example.com",
                source = {ip = "192.168.1.1"},
                timestamp = 1634567890000
            },
            expected_status = "Success"
        },
        {
            input = nil,
            expected_error = "Invalid input record"
        }
    }

    for i, test in ipairs(test_cases) do
        local result, err = transform(test.input)
        if err and test.expected_error and err == test.expected_error then
            print(string.format("Test %d: PASS", i))
        elseif result and result.status == test.expected_status then
            print(string.format("Test %d: PASS", i))
        else
            print(string.format("Test %d: FAIL", i))
        end
    end
end