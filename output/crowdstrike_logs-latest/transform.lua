-- CrowdStrike Parser: crowdstrike_logs-latest 
-- OCSF Class: Security Finding (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:57:50.244653

-- Pre-compile patterns for performance
local PATTERNS = {
    key = "^[%w_]+$",
    severity = "^%d+$"
}

-- Cached references for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_match = string.match
local string_format = string.format

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize output structure with nested tables
    local output = {
        class_uid = 1001,
        class_name = "Security Finding", 
        category_uid = 1,
        category_name = "Security Control",
        activity_id = 1,
        type_uid = 100101,
        device = {},
        metadata = {
            version = "1.0.0",
            product = {
                name = "CrowdStrike Falcon",
                vendor_name = "CrowdStrike"
            }
        }
    }

    -- Optimized field transformations using local references
    local device = output.device
    
    -- Device vendor mapping with validation
    if record.deviceVendor and string_match(record.deviceVendor, PATTERNS.key) then
        device.vendor = record.deviceVendor
    end

    -- Device product mapping with validation
    if record.deviceProduct and string_match(record.deviceProduct, PATTERNS.key) then
        device.product = record.deviceProduct
    end

    -- Severity casting with validation
    if record.severity then
        local sev = tonumber(record.severity)
        if sev and sev >= 0 and sev <= 10 then
            output.severity = sev
        end
    end

    -- Signature ID mapping with sanitization
    if record.signatureID then
        output.signature_id = string_format("%s", record.signatureID)
    end

    -- Timestamp handling
    output.time = record.time or (os_time() * 1000)

    -- Validation of required fields
    if not device.vendor or not device.product then
        return nil, "Missing required device fields"
    end

    -- Add observability metadata
    output.metadata.processing = {
        timestamp = os_time() * 1000,
        parser_version = "1.0.0"
    }

    return output
end

-- Error handler wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end

-- Optimization notes:
-- 1. Pattern pre-compilation reduces regex overhead
-- 2. Cached function references improve performance
-- 3. Local variables reduce table lookups
-- 4. Early validation prevents unnecessary processing
-- 5. Efficient string formatting with string.format
-- 6. Structured error handling with pcall wrapper