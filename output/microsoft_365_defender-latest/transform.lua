-- SentinelOne Parser: microsoft_365_defender-latest 
-- OCSF Class: Security Finding (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:06:08.134326

-- Pre-declare locals for performance
local type = type
local pairs = pairs
local os_time = os.time
local string_format = string.format

-- Cached validation patterns
local REQUIRED_FIELDS = {
    class_uid = true,
    category_uid = true,
    time = true
}

-- Error message templates
local ERROR_MESSAGES = {
    invalid_input = "Invalid input record",
    missing_required = "Missing required field: %s",
    invalid_type = "Invalid type for field %s: expected %s, got %s"
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, ERROR_MESSAGES.invalid_input
    end

    -- Initialize OCSF-compliant output with pre-allocated structure
    local output = {
        -- Core OCSF fields
        class_uid = 1001,
        class_name = "Security Finding",
        category_uid = 1, 
        category_name = "Findings",
        activity_id = 1,
        type_uid = 100101,
        
        -- Metadata
        metadata = {
            version = "1.0.0",
            product = {
                name = "Microsoft 365 Defender",
                vendor_name = "Microsoft"
            }
        }
    }

    -- Optimized field transformations using local references
    local device_events = record.deviceEvents
    if device_events then
        -- Direct assignment for performance
        output.device_events = device_events
        
        -- Extract common device event fields if present
        if type(device_events) == "table" then
            local first_event = device_events[1]
            if first_event then
                output.device_name = first_event.DeviceName
                output.device_id = first_event.DeviceId
            end
        end
    end

    -- Timestamp handling with validation
    local event_time = record.time or record.timestamp
    if event_time then
        output.time = tonumber(event_time)
    else
        output.time = os_time() * 1000 -- Convert to milliseconds
    end

    -- Validation of required fields
    for field, _ in pairs(REQUIRED_FIELDS) do
        if not output[field] then
            return nil, string_format(ERROR_MESSAGES.missing_required, field)
        end
    end

    -- Type validation for critical fields
    if type(output.class_uid) ~= "number" then
        return nil, string_format(ERROR_MESSAGES.invalid_type, "class_uid", "number", type(output.class_uid))
    end

    -- Add observability metadata
    output.observo_metadata = {
        parser_version = "latest",
        processing_time = os_time(),
        source_format = "JSON"
    }

    return output
end

-- Cache common string patterns
local function get_cached_pattern(pattern_key)
    local patterns = {
        timestamp = "^%d+$",
        device_id = "^[A-Fa-f0-9%-]+$"
    }
    return patterns[pattern_key]
end

-- Validation helper functions
local function validate_field_type(value, expected_type)
    return type(value) == expected_type
end

-- Error logging helper
local function log_error(error_type, details)
    -- Implement error logging based on Observo.ai requirements
    return string_format("[ERROR][M365-Defender] %s: %s", error_type, details)
end