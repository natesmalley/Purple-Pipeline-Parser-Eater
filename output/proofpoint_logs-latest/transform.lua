-- SentinelOne Parser: proofpoint_logs-latest
-- OCSF Class: Generic Log (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:09:22.770582

-- Pre-declare locals for performance optimization
local type = type
local os_time = os.time
local string_format = string.format
local table_insert = table.insert

-- Constants for OCSF classification
local OCSF_CLASS = {
    UID = 1001,
    NAME = "Generic Log",
    CATEGORY_UID = 1,
    CATEGORY_NAME = "System Activity",
    TYPE_UID = 100101
}

-- Validation helper functions
local function validate_record(record)
    if not record or type(record) ~= "table" then
        return false, "Invalid input record structure"
    end
    return true, nil
end

-- Main transformation function
function transform(record)
    -- Fast input validation
    local is_valid, err = validate_record(record)
    if not is_valid then
        return nil, err
    end

    -- Initialize output structure with local reference for performance
    local output = {
        -- OCSF mandatory fields
        class_uid = OCSF_CLASS.UID,
        class_name = OCSF_CLASS.NAME,
        category_uid = OCSF_CLASS.CATEGORY_UID,
        category_name = OCSF_CLASS.CATEGORY_NAME,
        type_uid = OCSF_CLASS.TYPE_UID,
        time = record.time or (os_time() * 1000),
        
        -- Metadata
        metadata = {
            version = "1.0.0",
            product = {
                name = "Proofpoint Logs",
                vendor_name = "Proofpoint"
            }
        }
    }

    -- Efficient raw log handling
    if record.raw_log then
        output.raw_data = record.raw_log
        
        -- Optional: Add hash for deduplication
        -- output.raw_data_hash = compute_hash(record.raw_log)
    end

    -- Error collection for partial failures
    local errors = {}
    
    -- Validate required fields
    if not output.class_uid or output.class_uid == 0 then
        table_insert(errors, "Invalid class_uid")
    end

    -- Return results with any validation errors
    if #errors > 0 then
        return output, string_format("Validation warnings: %s", table.concat(errors, "; "))
    end

    return output
end

-- Optional: Add debug/testing function
function debug_transform(record)
    local result, err = transform(record)
    if err then
        return string_format("Error: %s", err)
    end
    return result
end

--[[ Usage Examples:
local test_cases = {
    {
        input = {raw_log = "sample log entry"},
        expected = {class_uid = 1001, raw_data = "sample log entry"}
    },
    {
        input = nil,
        expected_error = "Invalid input record structure"
    }
}
--]]