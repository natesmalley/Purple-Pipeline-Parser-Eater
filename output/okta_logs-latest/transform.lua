-- SentinelOne Parser: okta_logs-latest
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:07:51.921177

-- Pre-declare locals for performance optimization
local type = type
local pairs = pairs
local os_time = os.time
local string_format = string.format
local table_insert = table.insert

-- Constants for OCSF fields
local OCSF_CONSTANTS = {
    CLASS_UID = 3002,
    CLASS_NAME = "Authentication",
    CATEGORY_UID = 3,
    CATEGORY_NAME = "Identity & Access Management"
}

-- Validation helper functions
local function validate_string(value)
    return type(value) == "string" and #value > 0
end

local function validate_number(value)
    return type(value) == "number"
end

function transform(record)
    -- Input validation with detailed error message
    if not record or type(record) ~= "table" then
        return nil, string_format("Invalid input record type: %s", type(record))
    end

    -- Initialize OCSF-compliant output structure with local reference
    local output = {
        class_uid = OCSF_CONSTANTS.CLASS_UID,
        class_name = OCSF_CONSTANTS.CLASS_NAME,
        category_uid = OCSF_CONSTANTS.CATEGORY_UID,
        category_name = OCSF_CONSTANTS.CATEGORY_NAME,
        activity_id = 1,
        type_uid = 300201,
        metadata = {
            version = "1.0.0",
            product = {
                name = "Okta Identity Cloud",
                vendor_name = "Okta"
            }
        }
    }

    -- Timestamp handling with validation
    local current_time = os_time() * 1000
    output.time = current_time
    output.observed_time = current_time

    -- Raw log handling with validation
    if record.raw_log then
        if validate_string(record.raw_log) then
            output.raw_data = record.raw_log
        else
            return nil, "Invalid raw_log format"
        end
    end

    -- Extract Okta-specific fields if present
    local okta_fields = {}
    local field_errors = {}
    
    -- Efficient field extraction with error collection
    for key, value in pairs(record) do
        if key:match("^okta_") then
            if validate_string(value) or validate_number(value) then
                okta_fields[key] = value
            else
                table_insert(field_errors, string_format("Invalid field %s", key))
            end
        end
    end

    -- Add extracted fields to output if valid
    if next(okta_fields) then
        output.extensions = {
            okta = okta_fields
        }
    end

    -- Final validation checks
    if #field_errors > 0 then
        return nil, string_format("Field validation errors: %s", table.concat(field_errors, ", "))
    end

    -- Ensure required OCSF fields are present
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Missing required OCSF class_uid"
    end

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