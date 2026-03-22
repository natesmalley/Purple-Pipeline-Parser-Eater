-- SentinelOne Parser: imperva_sonar-latest 
-- OCSF Class: Database Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:01:45.707688

-- Pre-declare locals for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_format = string.format

-- Validation constants
local REQUIRED_FIELDS = {
    timestamp = true
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Fast access to unmapped data
    local unmapped = record.unmapped
    if not unmapped then
        return nil, "Missing unmapped data structure"
    end

    -- Initialize OCSF-compliant output structure with local reference
    local output = {
        -- Static OCSF classification fields
        class_uid = 1001,
        class_name = "Database Activity", 
        category_uid = 1,
        category_name = "Security Control",
        activity_id = 1,
        type_uid = 100101,
        
        -- Metadata fields
        metadata = {
            product = {
                name = "Sonar",
                vendor_name = "Imperva"
            },
            version = "1.0.0"
        }
    }

    -- Timestamp handling with validation
    local timestamp = unmapped.timestamp
    if timestamp then
        -- Convert ISO8601 to epoch seconds
        local ts_num = tonumber(timestamp)
        if ts_num then
            output.time = ts_num
        else
            -- Fallback to current time if conversion fails
            output.time = os_time() * 1000
            output.parsing_error = string_format("Invalid timestamp format: %s", timestamp)
        end
    else
        output.time = os_time() * 1000
    end

    -- Additional field validations
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid OCSF classification"
    end

    -- Add observability metadata
    output._observo = {
        parser_version = "1.0.0",
        processing_time = os_time(),
        source = "imperva_sonar"
    }

    -- Performance optimization: batch return
    return output
end

-- Error handler wrapper
local function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end

-- Validation helper
local function validate_record(record)
    if not record then return false end
    for field in pairs(REQUIRED_FIELDS) do
        if not record[field] then return false end
    end
    return true
end

-- Export functions
return {
    transform = safe_transform,
    validate = validate_record
}