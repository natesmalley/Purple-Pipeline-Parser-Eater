--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: cloudflare_logs-latest
  Generated: 2025-10-13T12:49:17.109713
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: cloudflare_logs-latest 
-- OCSF Class: Network Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:16:09.199340

-- Pre-declare locals for performance
local type = type
local os_time = os.time
local error_msgs = {
    invalid_input = "Invalid input record",
    missing_timestamp = "Missing required EdgeStartTimestamp field",
    invalid_timestamp = "Invalid timestamp format"
}

-- Validation helper functions
local function validate_timestamp(ts)
    if not ts then return false end
    local n = tonumber(ts)
    return n and n > 0
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, error_msgs.invalid_input
    end

    -- Initialize output structure with local reference
    local output = {
        metadata = {},
        class_uid = 1001,
        class_name = "Network Activity", 
        category_uid = 1,
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = 100101,
        time = os_time() * 1000 -- Default timestamp
    }

    -- Timestamp handling with validation
    local edge_ts = record.EdgeStartTimestamp
    if edge_ts then
        if not validate_timestamp(edge_ts) then
            return nil, error_msgs.invalid_timestamp
        end
        output.metadata.timestamp = edge_ts
    else
        return nil, error_msgs.missing_timestamp
    end

    -- Optional Cloudflare-specific fields
    if record.ClientIP then
        output.src = {
            ip = record.ClientIP,
            port = record.ClientPort or 0
        }
    end

    if record.EdgeServerIP then
        output.dst = {
            ip = record.EdgeServerIP,
            port = record.EdgeServerPort or 0
        }
    end

    -- Add HTTP metadata if present
    if record.HttpRequest then
        output.http = {
            method = record.HttpRequest.method,
            url = record.HttpRequest.url,
            status_code = record.HttpResponse and record.HttpResponse.status or 0
        }
    end

    -- Performance optimization: batch field validation
    local required_fields = {
        "class_uid",
        "category_uid",
        "metadata"
    }
    
    for _, field in ipairs(required_fields) do
        if not output[field] then
            return nil, string.format("Missing required field: %s", field)
        end
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
            input = {
                EdgeStartTimestamp = "1634567890000",
                ClientIP = "1.2.3.4",
                EdgeServerIP = "5.6.7.8"
            },
            expected = true
        },
        {
            input = nil,
            expected = false
        },
        {
            input = {}, -- Missing required fields
            expected = false
        }
    }

    for i, test in ipairs(test_cases) do
        local result, err = safe_transform(test.input)
        if (result and test.expected) or (not result and not test.expected) then
            print(string.format("Test %d: PASS", i))
        else
            print(string.format("Test %d: FAIL - %s", i, err or ""))
        end
    end
end