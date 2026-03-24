-- SentinelOne Parser: microsoft_activedirectory_logs-latest 
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:06:10.366351

-- Pre-declare locals for performance
local type = type
local pairs = pairs
local os_time = os.time
local string_format = string.format

-- Validation constants
local REQUIRED_FIELDS = {
    "event_data"
}

-- Error messages
local ERROR_MESSAGES = {
    invalid_input = "Invalid input record",
    missing_required = "Missing required field: %s",
    invalid_class = "Invalid class_uid"
}

-- Helper function for deep copy (optimized for performance)
local function deep_copy(t)
    if type(t) ~= "table" then return t end
    local copy = {}
    for k, v in pairs(t) do
        copy[k] = type(v) == "table" and deep_copy(v) or v
    end
    return copy
end

-- Validate required fields
local function validate_record(record)
    if not record or type(record) ~= "table" then
        return false, ERROR_MESSAGES.invalid_input
    end
    
    for _, field in ipairs(REQUIRED_FIELDS) do
        if not record[field] then
            return false, string_format(ERROR_MESSAGES.missing_required, field)
        end
    end
    
    return true
end

function transform(record)
    -- Input validation with early return
    local is_valid, error_msg = validate_record(record)
    if not is_valid then
        return nil, error_msg
    end

    -- Initialize OCSF-compliant output structure
    local output = {
        class_uid = 3002,
        class_name = "Authentication",
        category_uid = 3,
        category_name = "Identity & Access Management",
        activity_id = 1,
        type_uid = 300201,
        time = record.time or (os_time() * 1000),
        metadata = {
            version = "1.0.0",
            product = {
                name = "Microsoft Active Directory",
                vendor_name = "Microsoft"
            }
        }
    }

    -- Optimized field transformations
    if record.event_data then
        -- Deep copy to prevent reference issues
        output.activity_data = deep_copy(record.event_data)
    end

    -- Enrich with additional context if available
    if record.source_ip then
        output.src_endpoint = {
            ip = record.source_ip,
            hostname = record.source_hostname
        }
    end

    -- Add observability metadata
    output._observo = {
        parser_version = "latest",
        ingestion_time = os_time() * 1000
    }

    -- Final validation
    if not output.class_uid or output.class_uid == 0 then
        return nil, ERROR_MESSAGES.invalid_class
    end

    return output
end

-- Error recovery function
local function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, "Transform error: " .. tostring(result)
    end
    return result
end

-- Export functions
return {
    transform = safe_transform,
    _transform = transform  -- For testing
}