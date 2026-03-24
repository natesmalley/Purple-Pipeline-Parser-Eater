--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: mock-windows-security
  Generated: 2025-10-08T23:41:18.453405
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: mock-windows-security
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-08T23:40:36.860415

-- Pre-declare locals for performance optimization
local type = type
local tonumber = tonumber
local os_time = os.time

-- Constant definitions for better performance and maintenance
local OCSF_CLASS = {
    UID = 3002,
    NAME = "Authentication",
    CATEGORY_UID = 3,
    CATEGORY_NAME = "Identity & Access Management"
}

-- Validation helper functions
local function validate_ip(ip)
    if not ip then return false end
    local parts = {ip:match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")}
    if #parts ~= 4 then return false end
    for _, part in ipairs(parts) do
        local num = tonumber(part)
        if not num or num < 0 or num > 255 then return false end
    end
    return true
end

local function validate_timestamp(ts)
    if not ts then return false end
    return ts:match("^%d%d%d%d%-%d%d%-%d%dT%d%d:%d%d:%d%dZ$") ~= nil
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure with nested tables
    local output = {
        class_uid = OCSF_CLASS.UID,
        class_name = OCSF_CLASS.NAME,
        category_uid = OCSF_CLASS.CATEGORY_UID,
        category_name = OCSF_CLASS.CATEGORY_NAME,
        user = {},
        src_endpoint = {}
    }

    -- Event ID transformation with validation
    local event_id = record.event_id
    if event_id then
        local num_event_id = tonumber(event_id)
        if num_event_id then
            output.event_uid = num_event_id
        end
    end

    -- Timestamp validation and transformation
    local timestamp = record.timestamp
    if timestamp and validate_timestamp(timestamp) then
        output.time = timestamp
    else
        output.time = os_time() * 1000
    end

    -- User name transformation with sanitization
    local user_name = record.user_name
    if user_name and type(user_name) == "string" then
        output.user.name = user_name:gsub("[^%w%s%-_@%.]", "")
    end

    -- Source IP transformation with validation
    local source_ip = record.source_ip
    if source_ip and validate_ip(source_ip) then
        output.src_endpoint.ip = source_ip
    end

    -- Action transformation with normalization
    local action = record.action
    if action and type(action) == "string" then
        output.activity_name = action:lower()
        -- Map common Windows actions to OCSF activity names
        if action == "login_success" then
            output.activity_id = 1
            output.status = "success"
        elseif action == "login_failure" then
            output.activity_id = 1
            output.status = "failure"
        end
    end

    -- Final validation of required fields
    if not output.event_uid then
        return nil, "Missing required field: event_uid"
    end

    return output
end

-- Error handling wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string.format("Transform error: %s", result)
    end
    return result
end