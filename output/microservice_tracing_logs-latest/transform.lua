-- SentinelOne Parser: microservice_tracing_logs-latest 
-- OCSF Class: Application Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:05:50.899843

-- Pre-declare locals for performance
local type = type
local os_time = os.time
local string_format = string.format
local table_insert = table.insert

-- Validation constants
local REQUIRED_FIELDS = {
    "raw_log"
}

-- Error messages
local ERROR_MESSAGES = {
    invalid_input = "Invalid input record",
    missing_required = "Missing required field: %s",
    invalid_class = "Invalid class_uid"
}

-- Optimized validation function
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
    -- Fast input validation
    local is_valid, error_msg = validate_record(record)
    if not is_valid then
        return nil, error_msg
    end

    -- Initialize OCSF output with pre-allocated structure
    local output = {
        -- OCSF mandatory fields
        class_uid = 1001,
        class_name = "Application Activity",
        category_uid = 1, 
        category_name = "Application",
        activity_id = 1,
        type_uid = 100101,
        
        -- Timestamp handling
        time = record.timestamp or (os_time() * 1000),
        
        -- Metadata
        metadata = {
            version = "1.0.0",
            product = {
                name = "microservice-logs",
                vendor_name = "generic"
            }
        }
    }

    -- Optimized field mapping
    output.raw_data = record.raw_log

    -- Optional field enrichment (if available)
    if record.service_name then
        output.service = {
            name = record.service_name
        }
    end

    -- Trace context (if available) 
    if record.trace_id then
        output.trace_data = {
            trace_id = record.trace_id,
            span_id = record.span_id,
            parent_span_id = record.parent_span_id
        }
    end

    -- Final validation
    if not output.class_uid or output.class_uid == 0 then
        return nil, ERROR_MESSAGES.invalid_class
    end

    return output
end

-- Error recovery wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, "Transform error: " .. tostring(result)
    end
    return result
end