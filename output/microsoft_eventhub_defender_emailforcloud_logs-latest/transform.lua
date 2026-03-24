-- SentinelOne Parser: microsoft_eventhub_defender_emailforcloud_logs-latest
-- OCSF Class: Security Finding (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:06:45.238539

-- Pre-declare locals for performance
local type = type
local pairs = pairs
local os_time = os.time
local string_format = string.format
local table_insert = table.insert

-- Validation constants
local REQUIRED_FIELDS = {
    "raw_event"
}

-- Error messages
local ERROR_MESSAGES = {
    invalid_input = "Invalid input record",
    missing_required = "Missing required field: %s",
    invalid_type = "Invalid type for field %s, expected %s got %s"
}

-- Validation helper functions
local function validate_field_type(value, expected_type, field_name)
    if type(value) ~= expected_type then
        return false, string_format(ERROR_MESSAGES.invalid_type, field_name, expected_type, type(value))
    end
    return true
end

local function validate_required_fields(record)
    for _, field in pairs(REQUIRED_FIELDS) do
        if not record[field] then
            return false, string_format(ERROR_MESSAGES.missing_required, field)
        end
    end
    return true
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, ERROR_MESSAGES.invalid_input
    end

    -- Validate required fields
    local valid, err = validate_required_fields(record)
    if not valid then
        return nil, err
    end

    -- Initialize OCSF-compliant output structure with local references
    local output = {
        -- OCSF Classification
        class_uid = 1001,
        class_name = "Security Finding",
        category_uid = 1,
        category_name = "Security Control",
        activity_id = 1,
        type_uid = 100101,
        
        -- Metadata
        metadata = {
            version = "1.0.0",
            product = {
                name = "Microsoft Defender for Email/Cloud",
                vendor_name = "Microsoft"
            }
        },

        -- Timestamp handling
        time = record.time or (os_time() * 1000),
        
        -- Raw event preservation
        raw_event = record.raw_event
    }

    -- Validation and type checking for raw_event
    if record.raw_event then
        local valid, err = validate_field_type(record.raw_event, "string", "raw_event")
        if not valid then
            return nil, err
        end
    end

    -- Add observability metadata
    output.observo_metadata = {
        parser_version = "1.0.0",
        processing_time = os_time(),
        source = "microsoft_eventhub_defender_emailforcloud"
    }

    -- Final validation
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
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