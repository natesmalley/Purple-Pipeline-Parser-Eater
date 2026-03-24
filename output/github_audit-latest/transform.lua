--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: github_audit-latest
  Generated: 2025-10-13T12:56:53.299444
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: github_audit-latest
-- OCSF Class: DevOps Activity (8001) 
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:19:15.616715

-- Pre-declare locals for performance
local type = type
local pairs = pairs
local os_time = os.time
local string_format = string.format

-- Validation helper functions
local function validate_ip(ip)
    if not ip then return false end
    local parts = {ip:match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")}
    if #parts ~= 4 then return false end
    for _, part in pairs(parts) do
        local n = tonumber(part)
        if not n or n < 0 or n > 255 then return false end
    end
    return true
end

function transform(record)
    -- Input validation with detailed error messages
    if not record then
        return nil, "Record is nil"
    end
    if type(record) ~= "table" then
        return nil, string_format("Expected table, got %s", type(record))
    end

    -- Initialize OCSF output with static fields
    local output = {
        -- Core OCSF classification
        class_uid = 8001,
        class_name = "DevOps Activity",
        category_uid = 8,
        category_name = "System Activity",
        type_uid = 800101,
        activity_id = 1,
        severity_id = 1,
        
        -- Initialize nested structures
        user = {},
        src_endpoint = {},
        metadata = {},
        resource = {}
    }

    -- Timestamp handling with validation
    if record.timestamp then
        local ts = tonumber(record.timestamp)
        if ts then
            output.time = ts
        else
            output.time = os_time() * 1000
        end
    else
        output.time = os_time() * 1000
    end

    -- User information
    if record.actor then
        output.user.name = record.actor
    end

    -- Source IP validation and assignment
    if record.source_ip and validate_ip(record.source_ip) then
        output.src_endpoint.ip = record.source_ip
    end

    -- Organization/tenant mapping
    if record.org then
        output.metadata.tenant_uid = record.org
    end

    -- Repository resource mapping
    if record.repository then
        output.resource.name = record.repository
    end

    -- Activity details
    if record.action then
        output.activity_name = record.action
    end

    -- Status mapping
    if record.outcome then
        output.status = record.outcome
    end

    -- Message/description field
    if record.description then
        output.message = record.description
    end

    -- Final validation of required fields
    if not output.activity_name then
        return nil, "Missing required field: activity_name"
    end

    if not output.user.name then
        return nil, "Missing required field: user.name"
    end

    return output
end

-- Error handler wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end