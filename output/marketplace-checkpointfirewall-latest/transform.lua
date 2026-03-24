--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: marketplace-checkpointfirewall-latest
  Generated: 2025-10-13T12:43:20.939547
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: marketplace-checkpointfirewall-latest
-- OCSF Class: Network Activity (6003)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:05:30.986104

-- Pre-declare locals for performance optimization
local type = type
local pairs = pairs
local tonumber = tonumber
local os_time = os.time
local json_decode = require("cjson").decode

-- Constant definitions for better maintenance and performance
local CONSTANTS = {
    CLASS_UID = 6003,
    CATEGORY_UID = 6,
    ACTIVITY_ID = 99,
    TYPE_UID = 600301
}

-- Field validation helper functions
local function validate_string(value)
    return type(value) == "string" and value ~= "" and value or nil
end

local function validate_number(value)
    local num = tonumber(value)
    return num and num > 0 and num or nil
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure with local reference
    local output = {
        class_uid = CONSTANTS.CLASS_UID,
        category_uid = CONSTANTS.CATEGORY_UID,
        activity_id = CONSTANTS.ACTIVITY_ID,
        type_uid = CONSTANTS.TYPE_UID,
        metadata = {
            version = "1.0.0",
            product = {
                name = "Check Point Next Generation Firewall",
                vendor = "Check Point",
                feature = {
                    name = "Network Security",
                    uid = 1
                }
            }
        }
    }

    -- Parse JSON payload if present
    local payload = record.json_payload
    if payload and type(payload) == "string" then
        local success, parsed = pcall(json_decode, payload)
        if not success then
            return nil, "Invalid JSON payload"
        end
        record = parsed
    end

    -- Map Check Point specific fields to OCSF schema
    -- Using local references for frequently accessed paths
    local src = record.source or {}
    local dst = record.destination or {}

    -- Network context mapping
    output.src = {
        ip = validate_string(src.ip),
        port = validate_number(src.port),
        hostname = validate_string(src.hostname)
    }

    output.dst = {
        ip = validate_string(dst.ip),
        port = validate_number(dst.port),
        hostname = validate_string(dst.hostname)
    }

    -- Event specific details
    output.severity = validate_number(record.severity) or 0
    output.status = validate_string(record.status) or "UNKNOWN"
    output.message = validate_string(record.message)

    -- Timestamp handling
    local event_time = validate_number(record.time)
    output.time = event_time or (os_time() * 1000)

    -- Validation of required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    -- Clean up nil values for better serialization
    for k, v in pairs(output) do
        if v == nil then
            output[k] = nil
        end
    end

    return output
end

-- Error handling wrapper for production use
function safe_transform(record)
    local success, result, error = pcall(transform, record)
    if not success then
        return nil, "Transform function error: " .. tostring(result)
    end
    return result, error
end