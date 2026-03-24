-- SentinelOne Parser: sample_test_logs-latest
-- OCSF Class: Generic Log (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:10:03.041470

-- Pre-declare locals for performance optimization
local type = type
local os_time = os.time
local error_msgs = {
    invalid_input = "Invalid input record",
    missing_class = "Invalid class_uid",
    malformed_data = "Malformed data structure"
}

-- Validation helper function
local function validate_record(record)
    if not record or type(record) ~= "table" then
        return false, error_msgs.invalid_input
    end
    return true
end

function transform(record)
    -- Fast input validation with early return
    local is_valid, err = validate_record(record)
    if not is_valid then
        return nil, err
    end

    -- Initialize OCSF-compliant output structure with local reference
    local output = {
        -- Required OCSF fields
        class_uid = 1001,
        class_name = "Generic Log",
        category_uid = 1,
        category_name = "System Activity",
        activity_id = 1,
        type_uid = 100101,
        metadata = {
            version = "1.0.0",
            product = {
                name = "Generic Logs",
                vendor_name = "Generic"
            }
        }
    }

    -- Efficient raw_log handling with null check
    if record.raw_log ~= nil then
        output.raw_log = record.raw_log
    end

    -- Add timestamp if not present (millisecond precision)
    if not output.time then
        output.time = os_time() * 1000
    end

    -- Validate required fields before return
    if not output.class_uid or output.class_uid == 0 then
        return nil, error_msgs.missing_class
    end

    -- Optional: Add observability metadata
    output.metadata.processing = {
        parser_version = "latest",
        processing_time = os_time()
    }

    return output
end

-- Error recovery function for malformed data
local function recover_malformed_data(record)
    if type(record) == "string" then
        return {
            raw_log = record,
            recovered = true
        }
    end
    return nil
end

-- Optimization notes:
-- 1. Local variable declarations for core functions
-- 2. Pre-compiled error messages
-- 3. Minimal table operations
-- 4. Early validation pattern
-- 5. Efficient timestamp handling
-- 6. No global state