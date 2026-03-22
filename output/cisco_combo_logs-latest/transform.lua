--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: cisco_combo_logs-latest
  Generated: 2025-10-13T12:46:31.185712
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: cisco_combo_logs-latest 
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:15:24.729500

-- Pre-compile patterns for performance
local IPv4_PATTERN = "^(%d%d?%d?)%.(%d%d?%d?)%.(%d%d?%d?)%.(%d%d?%d?)$"
local IPv6_PATTERN = "^%x+:[%x:]+$"

-- Cached functions for performance
local type = type
local tonumber = tonumber
local format = string.format
local time = os.time

-- Validation helper functions
local function validate_ip(ip)
    if not ip then return false end
    
    -- Check IPv4
    local a,b,c,d = ip:match(IPv4_PATTERN)
    if a then
        a,b,c,d = tonumber(a),tonumber(b),tonumber(c),tonumber(d)
        return a and a <= 255 and b <= 255 and c <= 255 and d <= 255
    end
    
    -- Check IPv6
    return ip:match(IPv6_PATTERN) ~= nil
end

function transform(record)
    -- Input validation with detailed error messages
    if not record then
        return nil, "Record is nil"
    end
    if type(record) ~= "table" then
        return nil, format("Invalid record type: %s", type(record))
    end

    -- Initialize OCSF-compliant output with local references
    local output = {
        class_uid = 3002,
        class_name = "Authentication",
        category_uid = 3, 
        category_name = "Identity & Access Management",
        activity_id = 1,
        type_uid = 300201,
        time = record.timestamp or (time() * 1000),
        metadata = {
            product = {
                name = "Cisco ASA/FTD",
                vendor_name = "Cisco"
            },
            version = "1.0.0"
        },
        event = {},
        user = {},
        src_endpoint = {},
        dst_endpoint = {}
    }

    -- Optimized field transformations using local references
    local event, user, src_endpoint = output.event, output.user, output.src_endpoint

    -- Map event_id with validation
    if record.event_id then
        event.code = record.event_id
        event.name = format("Cisco Event %s", record.event_id)
    end

    -- Map user fields with validation
    if record.user then
        user.name = record.user
        user.type = "User"
    end

    -- Map source IP with validation
    if record.src_ip and validate_ip(record.src_ip) then
        src_endpoint.ip = record.src_ip
        if record.src_port then
            src_endpoint.port = tonumber(record.src_port)
        end
    end

    -- Additional field mappings based on event type
    if record.connection_type then
        event.category = record.connection_type
    end

    if record.msg then
        event.message = record.msg
    end

    -- Validation of required OCSF fields
    if not event.code then
        return nil, "Missing required field: event.code"
    end

    -- Clean empty tables for efficiency
    if not next(user) then output.user = nil end
    if not next(src_endpoint) then output.src_endpoint = nil end
    if not next(event) then output.event = nil end

    return output
end

-- Error recovery function
local function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, format("Transform error: %s", result)
    end
    return result
end

-- Batch processing optimization
function transform_batch(records)
    local results = {}
    local errors = {}
    
    for i, record in ipairs(records) do
        local result, err = safe_transform(record)
        if result then
            results[#results + 1] = result
        else
            errors[#errors + 1] = {index = i, error = err}
        end
    end
    
    return results, errors
end