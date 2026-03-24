-- SentinelOne Parser: pingprotect-latest
-- OCSF Class: Authentication (3002) 
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:09:21.768688

-- Pre-allocate static values for performance
local OCSF_CLASS_UID = 3002
local OCSF_CLASS_NAME = "Authentication"
local OCSF_CATEGORY_UID = 3
local OCSF_CATEGORY_NAME = "Identity & Access Management"

-- Validation helper functions
local function validate_string(str)
    return type(str) == "string" and str ~= ""
end

local function validate_number(num)
    return type(num) == "number" and num > 0
end

function transform(record)
    -- Input validation with detailed error message
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record: expected table, got " .. type(record)
    end

    -- Initialize OCSF-compliant output structure with local reference
    local output = {
        class_uid = OCSF_CLASS_UID,
        class_name = OCSF_CLASS_NAME,
        category_uid = OCSF_CATEGORY_UID,
        category_name = OCSF_CATEGORY_NAME,
        activity_id = 1,
        type_uid = 300201,
        metadata = {
            version = "1.0.0",
            product = {
                name = "PingProtect",
                vendor_name = "Ping"
            }
        }
    }

    -- Extract authentication details with error handling
    local auth_status = record.status or record.auth_status
    if validate_string(auth_status) then
        output.status = string.lower(auth_status)
    end

    -- Handle user information
    if record.user then
        output.user = {
            name = record.user.name or record.user.username,
            uid = record.user.id or record.user.uid,
            type = "User"
        }
    end

    -- Process authentication metadata
    if record.auth_metadata then
        output.auth_metadata = {
            auth_protocol = record.auth_metadata.protocol,
            auth_type = record.auth_metadata.type or "Unknown"
        }
    end

    -- Handle timestamp with microsecond precision
    local event_time = record.time or record.timestamp or record.event_time
    if validate_number(event_time) then
        output.time = event_time
    else
        output.time = os.time() * 1000 -- Default to current time in ms
    end

    -- Validate required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid configuration"
    end

    -- Add severity if present
    if record.severity and validate_string(record.severity) then
        output.severity = string.lower(record.severity)
    end

    -- Add source information
    output.src = {
        ip = record.src_ip or record.source_ip,
        port = record.src_port or record.source_port
    }

    -- Performance optimization: batch field assignments
    output.observability = {
        parser_version = "1.0.0",
        ingestion_time = os.time() * 1000,
        processing_time = 0 -- Placeholder for processing duration
    }

    return output
end

-- Error handling wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string.format("Transform error: %s", result)
    end
    return result
end