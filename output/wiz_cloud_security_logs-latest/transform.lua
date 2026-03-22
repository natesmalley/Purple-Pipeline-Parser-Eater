--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: wiz_cloud_security_logs-latest
  Generated: 2025-10-13T12:40:07.387742
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: wiz_cloud_security_logs-latest 
-- OCSF Class: Cloud Security (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:04:58.857195

-- Pre-declare locals for performance
local type = type
local pairs = pairs
local pcall = pcall
local cjson = require("cjson")
local string_format = string.format
local os_time = os.time

-- Cache common strings
local ERR_INVALID_INPUT = "Invalid input record"
local ERR_INVALID_JSON = "Invalid JSON in body field"
local ERR_MISSING_RECORDS = "Missing Records array"

-- Optimized JSON decode with error handling
local function safe_json_decode(str)
    if not str then return nil end
    local status, result = pcall(cjson.decode, str)
    return status and result or nil
end

-- Efficient body field parser
local function parse_body(body_str)
    if not body_str then return {} end
    
    -- Unescape JSON string
    body_str = body_str:gsub('\\"', '"')
    local body_data = safe_json_decode(body_str)
    return body_data or {}
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, ERR_INVALID_INPUT
    end

    -- Initialize OCSF-compliant output structure
    local output = {
        class_uid = 1001,
        class_name = "Cloud Security",
        category_uid = 1,
        category_name = "Cloud Infrastructure",
        activity_id = 1,
        type_uid = 100101,
        metadata = {
            product = {
                name = "Wiz Cloud Security Platform",
                vendor = "Wiz"
            },
            version = "1.0"
        }
    }

    -- Process Records array
    local records = record.Records
    if not records or type(records) ~= "table" then
        return nil, ERR_MISSING_RECORDS
    end

    -- Initialize events array
    local events = {}
    
    -- Process each record
    for _, rec in pairs(records) do
        -- Parse body field if present
        if rec.body then
            local body_data = parse_body(rec.body)
            
            -- Create event entry
            local event = {
                message_data = body_data,
                time = body_data.timestamp or (os_time() * 1000),
                severity = body_data.severity or "INFO",
                status = body_data.status or "UNKNOWN"
            }
            
            -- Add to events array
            events[#events + 1] = event
        end
    end

    -- Add events to output
    output.events = events
    
    -- Validation and cleanup
    if #events == 0 then
        return nil, "No valid events found"
    end

    -- Add timestamp if not present
    if not output.time then
        output.time = os_time() * 1000
    end

    return output
end

-- Error handler wrapper
function safe_transform(record)
    local status, result, err = pcall(transform, record)
    if not status then
        return nil, string_format("Transform error: %s", result)
    end
    return result, err
end