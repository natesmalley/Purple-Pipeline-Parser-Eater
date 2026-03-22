-- SentinelOne Parser: rubrik_backup_logs-latest 
-- OCSF Class: System Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:10:02.039085

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
        class_name = "System Activity",
        category_uid = 1, 
        category_name = "System",
        activity_id = 1,
        type_uid = 100101,
        
        -- Metadata
        metadata = {
            product = {
                name = "Rubrik Backup System",
                vendor_name = "Rubrik"
            },
            version = "1.0"
        },
        
        -- Timestamp handling
        time = os_time() * 1000
    }

    -- Optimized field mappings
    if record.raw_log then
        output.raw_data = record.raw_log -- Direct assignment for performance
    end

    -- Add any parsed backup status information
    if record.status then
        output.status = record.status
    end

    -- Validation and cleanup
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

-- Performance test helper
function benchmark(iterations)
    local start = os_time()
    local test_record = {raw_log = "test data"}
    
    for i=1,iterations do
        safe_transform(test_record)
    end
    
    return os_time() - start
end