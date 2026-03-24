-- SentinelOne Parser: cisco_duo-latest
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:53:23.132776

-- Pre-allocate constant strings for performance
local INVALID_INPUT = "Invalid input record"
local INVALID_CLASS = "Invalid class_uid"
local CLASS_UID = 3002
local CATEGORY_UID = 3

-- Optimized validation helper
local function validate_field(field, field_type)
    if not field then return false end
    return type(field) == field_type
end

function transform(record)
    -- Input validation with early return
    if not validate_field(record, "table") then
        return nil, INVALID_INPUT
    end

    -- Initialize output structure using local table
    local output = {
        -- Constants assigned once
        class_uid = CLASS_UID,
        class_name = "Authentication", 
        category_uid = CATEGORY_UID,
        category_name = "Identity & Access Management",
        activity_id = 1,
        type_uid = 300201,
        
        -- Initialize nested structures
        user = {},
        src_endpoint = {
            location = {}
        }
    }

    -- Safe table access helper
    local function safe_copy(from_path, to_table, to_field)
        local value = from_path
        if value ~= nil then
            to_table[to_field] = value
        end
    end

    -- Optimized field copying with null checks
    if record.unmapped then
        local unmapped = record.unmapped -- Local reference
        
        -- Timestamp handling
        safe_copy(unmapped.timestamp, output, "timestamp")
        safe_copy(unmapped.time, output, "time")

        -- User information
        if unmapped.user then
            safe_copy(unmapped.user.name, output.user, "name")
            safe_copy(unmapped.user.account_uid, output.user, "account_uid")
            safe_copy(unmapped.user.account_type, output.user, "account_type")
        end

        -- Source endpoint information
        if unmapped.src_endpoint then
            local src = unmapped.src_endpoint
            safe_copy(src.ip, output.src_endpoint, "ip")
            
            if src.location then
                safe_copy(src.location.desc, output.src_endpoint.location, "desc")
                safe_copy(src.location.city, output.src_endpoint.location, "city")
                safe_copy(src.location.country, output.src_endpoint.location, "country")
            end
        end

        -- Authentication details
        safe_copy(unmapped.auth_protocol, output, "auth_protocol")
        safe_copy(unmapped.auth_protocol_id, output, "auth_protocol_id")
        safe_copy(unmapped.mfa_factors, output, "mfa_factors")
        safe_copy(unmapped.status, output, "status")
        safe_copy(unmapped.status_id, output, "status_id")
        safe_copy(unmapped.message, output, "message")
    end

    -- Validation of required fields
    if not output.class_uid or output.class_uid ~= CLASS_UID then
        return nil, INVALID_CLASS
    end

    -- Ensure timestamp exists
    if not output.time then
        output.time = os.time() * 1000
    end

    -- Clean empty nested tables
    if next(output.user) == nil then output.user = nil end
    if next(output.src_endpoint.location) == nil then
        output.src_endpoint.location = nil
        if next(output.src_endpoint) == nil then
            output.src_endpoint = nil
        end
    end

    return output
end