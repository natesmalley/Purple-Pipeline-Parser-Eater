-- SentinelOne Parser: beyondtrust_privilegemgmtwindows_logs-latest 
-- OCSF Class: Privilege Management (3001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:52:18.531430

-- Pre-declare locals for performance
local type = type
local pairs = pairs
local tonumber = tonumber
local os_time = os.time
local string_format = string.format

-- Validation helper functions
local function validate_string(str)
    return type(str) == "string" and str ~= ""
end

local function validate_number(num)
    return type(num) == "number" and num > 0
end

-- Main transform function
function transform(record)
    -- Input validation with detailed error message
    if not record or type(record) ~= "table" then
        return nil, string_format("Invalid input record type: %s", type(record))
    end

    -- Initialize OCSF-compliant output structure with local reference
    local output = {
        -- Required OCSF fields
        class_uid = 3001,
        class_name = "Privilege Management",
        category_uid = 3, 
        category_name = "Identity & Access Management",
        activity_id = 1,
        type_uid = 300101,
        
        -- Nested structures
        metadata = {
            version = "1.0.0",
            product = {
                name = "BeyondTrust Privilege Management",
                vendor = "BeyondTrust"
            }
        },
        
        -- Initialize nested objects
        user = {},
        device = {},
        access = {}
    }

    -- Optimized field transformations using local references
    local access_activity = record.access_activity or {}
    local user = record.user or {}
    local device = record.device or {}

    -- Transform timestamp with validation
    if validate_string(access_activity.time_dt) then
        local timestamp = tonumber(access_activity.time_dt)
        output.time = timestamp or (os_time() * 1000)
    else
        output.time = os_time() * 1000
    end

    -- Transform user fields with validation
    if validate_string(user.name) then
        output.user.name = user.name
        output.user.type = "User" -- Default type
    end

    -- Transform device fields with validation
    if validate_string(device.name) then
        output.device.name = device.name
    end

    -- Additional security context
    if validate_string(access_activity.activity_id) then
        output.access.activity_id = access_activity.activity_id
    end

    -- Enrich with application details if available
    if validate_string(access_activity.app_desc) then
        output.application = {
            name = access_activity.app_desc,
            type = access_activity.app_type or "Unknown"
        }
    end

    -- Validation and cleanup
    if not validate_number(output.class_uid) then
        return nil, "Invalid class_uid"
    end

    -- Add observability metadata
    output.metadata.processing = {
        timestamp = os_time() * 1000,
        parser_version = "1.0.0"
    }

    return output
end

-- Error wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end