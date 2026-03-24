-- SentinelOne Parser: hypr_auth-latest
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:01:44.698518

-- Pre-compile patterns for performance
local ACTIVITY_PATTERNS = {
    AUTHENTICATION = true,
    REGISTRATION = true, 
    VERIFICATION = true,
    ENROLLMENT = true,
    REVOCATION = true
}

-- Cached activity mappings
local ACTIVITY_MAPPINGS = {
    AUTHENTICATION = {id = 1, name = "Logon"},
    REGISTRATION = {id = 99, name = "Other"},
    VERIFICATION = {id = 99, name = "Other"},
    ENROLLMENT = {id = 99, name = "Other"},
    REVOCATION = {id = 99, name = "Other"}
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local variables
    local output = {
        -- Core OCSF fields
        class_uid = 3002,
        class_name = "Authentication",
        category_uid = 3, 
        category_name = "Identity & Access Management",
        type_uid = 300201,
        severity_id = 1,
        severity = "Informational",

        -- Initialize nested objects
        user = {},
        device = {},
        metadata = {
            product = {
                vendor_name = "HYPR",
                name = "HYPR Authentication"
            },
            version = "1.0.0"
        }
    }

    -- Timestamp handling with validation
    if record.timestamp then
        local ts = tonumber(record.timestamp)
        if ts then
            output.time = ts
        else
            output.time = os.time() * 1000
        end
    end

    -- Activity mapping with optimization
    if record.event_type then
        local activity = ACTIVITY_MAPPINGS[record.event_type]
        if activity then
            output.activity_id = activity.id
            output.activity_name = activity.name
        end
    end

    -- User information handling
    if record.user then
        output.user.email_addr = record.user
        output.user.name = record.user -- Copy email as username
    end

    -- Device handling
    if record.device then
        output.device.name = record.device
    end

    -- Status mapping with boolean conversion
    if record.is_successful then
        local success = record.is_successful == "true"
        output.status_id = success and 1 or 2
        output.status = success and "Success" or "Failure"
    end

    -- Authentication protocol
    if record.authenticator then
        output.auth_protocol = record.authenticator
    end

    -- Message field
    if record.message then
        output.message = record.message
    end

    -- Validation of required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    if not output.time then
        output.time = os.time() * 1000
    end

    return output
end

-- Error handler wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string.format("Transform error: %s", result)
    end
    return result
end