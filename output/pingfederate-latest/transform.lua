-- SentinelOne Parser: pingfederate-latest 
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:08:48.965270

-- Pre-declare locals for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_format = string.format

-- Severity level mapping cache
local SEVERITY_MAP = {
    DEBUG = 1,
    INFO = 2, 
    WARN = 3,
    ERROR = 4,
    FATAL = 5
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure with local reference
    local output = {
        -- Required OCSF fields
        class_uid = 3002,
        class_name = "Authentication",
        category_uid = 3,
        category_name = "Identity & Access Management",
        activity_id = 1,
        type_uid = 300201,
        metadata = {
            version = "1.0.0",
            product = {
                name = "PingFederate",
                vendor_name = "PingIdentity"
            }
        }
    }

    -- Timestamp transformation with validation
    local timestamp = record.timestamp
    if timestamp then
        local ts_num = tonumber(timestamp)
        if ts_num then
            output.time = ts_num
        else
            -- Invalid timestamp format, use current time
            output.time = os_time() * 1000
            output.metadata.parsing_errors = {
                string_format("Invalid timestamp format: %s", timestamp)
            }
        end
    else
        output.time = os_time() * 1000
    end

    -- Severity mapping with validation
    local log_level = record.log_level
    if log_level then
        output.severity = SEVERITY_MAP[log_level:upper()] or 2 -- Default to INFO if unknown
    end

    -- Extract authentication details if present
    local auth_status = record.status or record.auth_status
    if auth_status then
        output.status = string.lower(auth_status) == "success" and "success" or "failure"
        output.status_code = output.status == "success" and 0 or 1
    end

    -- Capture user identity information
    if record.username then
        output.actor = {
            user = {
                name = record.username,
                type = "User"
            }
        }
    end

    -- Validation of required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Missing required OCSF class_uid"
    end

    if not output.time then
        return nil, "Missing required timestamp"
    end

    -- Add processing metadata
    output.metadata.processed_at = os_time() * 1000
    
    return output
end

-- Error handling wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end

-- Optimization notes:
-- 1. Local variable declarations for core functions
-- 2. Cached severity mapping table
-- 3. Early validation and returns
-- 4. Efficient string operations using string.format
-- 5. Minimal table allocations
-- 6. Structured error handling