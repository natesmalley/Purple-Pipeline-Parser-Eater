-- SentinelOne Parser: paloalto_logs-latest 
-- OCSF Class: Security Event (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:08:29.580523

-- Pre-declare locals for performance
local type = type
local os_time = os.time
local string_format = string.format
local error_msgs = {
    invalid_input = "Invalid input record",
    missing_required = "Missing required field: %s",
    invalid_class = "Invalid class_uid"
}

-- Validation helper functions
local function validate_record(record)
    if not record or type(record) ~= "table" then
        return false, error_msgs.invalid_input
    end
    return true
end

local function validate_required_fields(output)
    if not output.class_uid or output.class_uid == 0 then
        return false, error_msgs.invalid_class
    end
    return true
end

function transform(record)
    -- Input validation with early return
    local valid, err = validate_record(record)
    if not valid then
        return nil, err
    end

    -- Initialize OCSF-compliant output structure with local references
    local output = {
        -- Required OCSF fields
        class_uid = 1001,
        class_name = "Security Event",
        category_uid = 1, 
        category_name = "Security Control",
        activity_id = 1,
        type_uid = 100101,
        metadata = {
            version = "1.0.0",
            product = {
                name = "PAN-OS",
                vendor_name = "Palo Alto Networks"
            }
        }
    }

    -- Performance-optimized field transformations
    -- Using local references to record fields for faster access
    local raw_log = record.raw_log
    if raw_log then
        output.raw_event = raw_log
    end

    -- Add timestamp if not present (using pre-declared os_time)
    if not output.time then
        output.time = os_time() * 1000
    end

    -- Validation before return
    local valid, err = validate_required_fields(output)
    if not valid then
        return nil, err
    end

    -- Optional debug logging when enabled
    if _DEBUG then
        log_debug(string_format("Transformed PAN-OS event: %s", output.raw_event and #output.raw_event or 0))
    end

    return output
end

-- Error recovery function
local function recover_from_error(err_type, context)
    if _DEBUG then
        log_debug(string_format("Error recovery triggered: %s, Context: %s", err_type, context))
    end
    return nil, string_format("Recovery failed: %s", err_type)
end

-- Optimization notes:
-- 1. Local variable declarations for core functions
-- 2. Pre-compiled error messages
-- 3. Separate validation functions for better organization
-- 4. Minimal string operations
-- 5. Early validation and return
-- 6. No global state
-- 7. Efficient table initialization
-- 8. Debug logging only when enabled