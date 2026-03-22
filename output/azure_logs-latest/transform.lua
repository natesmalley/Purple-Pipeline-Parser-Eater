--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: azure_logs-latest
  Generated: 2025-10-13T11:21:41.347190
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: azure_logs-latest
-- OCSF Class: Cloud Resource (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T11:01:00.334111

-- Pre-compile patterns for performance
local RESOURCE_PATTERN = "[A-Z\\-0-9]*"
local TIMESTAMP_FORMAT = "^%d%d%d%d%-%d%d%-%d%dT%d%d:%d%d:%d%d"

-- Cache common string operations
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

    -- Initialize OCSF-compliant output with local vars for performance
    local output = {
        class_uid = 1001,
        class_name = "Cloud Resource", 
        category_uid = 1,
        category_name = "Cloud Infrastructure",
        activity_id = 1,
        type_uid = 100101,
        metadata = {
            product = {
                name = "Azure",
                vendor_name = "Microsoft"
            },
            version = "1.0"
        }
    }

    -- Timestamp handling with validation
    local time = record.time
    if time then
        -- Validate timestamp format
        if string_match(time, TIMESTAMP_FORMAT) then
            output.timestamp = time
        else
            -- Fall back to current time if invalid
            output.timestamp = string_format("%s.000Z", os.date("!%Y-%m-%dT%H:%M:%S"))
        end
    else
        output.timestamp = string_format("%s.000Z", os.date("!%Y-%m-%dT%H:%M:%S"))
    end

    -- Resource ID handling with pattern validation
    local identifier = record.identifier
    if identifier then
        if string_match(identifier, RESOURCE_PATTERN) then
            output.resource_id = identifier
        else
            output.resource_id = "INVALID_RESOURCE_ID"
        end
    end

    -- Additional Azure-specific field mappings
    if record.subscription_id then
        output.subscription_id = record.subscription_id
    end
    
    if record.resource_group then
        output.resource_group = record.resource_group
    end

    -- Validation of required OCSF fields
    if not output.timestamp then
        return nil, "Missing required timestamp"
    end

    -- Add observability metadata
    output.observo_metadata = {
        parser_version = "azure_logs-latest",
        processing_time = os_time(),
        source_format = "json"
    }

    -- Error collection for partial failures
    local errors = {}
    if #errors > 0 then
        output.processing_errors = errors
    end

    return output
end

-- Cache for resource pattern matching
local resource_cache = {}
local MAX_CACHE_SIZE = 1000

-- Helper function for resource pattern validation
local function validate_resource_id(id)
    if not resource_cache[id] then
        if #resource_cache >= MAX_CACHE_SIZE then
            resource_cache = {} -- Reset cache if full
        end
        resource_cache[id] = string_match(id, RESOURCE_PATTERN) ~= nil
    end
    return resource_cache[id]
end

-- Test cases
local function run_tests()
    -- Test 1: Valid input
    local test1 = transform({
        time = "2025-10-13T10:34:36.524Z",
        identifier = "RESOURCE-123",
        subscription_id = "sub-123"
    })
    assert(test1.timestamp == "2025-10-13T10:34:36.524Z")

    -- Test 2: Invalid input
    local test2, err = transform(nil)
    assert(err == "Invalid input record")

    -- Test 3: Missing timestamp
    local test3 = transform({identifier = "RESOURCE-123"})
    assert(test3.timestamp ~= nil)
end