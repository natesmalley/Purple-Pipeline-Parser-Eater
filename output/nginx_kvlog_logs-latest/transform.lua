-- SentinelOne Parser: nginx_kvlog_logs-latest 
-- OCSF Class: HTTP Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:07:50.916594

-- Pre-declare locals for performance
local type = type
local os_time = os.time
local string_format = string.format
local error_msgs = {
    invalid_input = "Invalid input record",
    invalid_class = "Invalid class_uid",
    malformed_request = "Malformed request field"
}

-- Cache commonly used values
local OCSF_CLASS = {
    uid = 1001,
    name = "HTTP Activity",
    category_uid = 1, 
    category_name = "Network Activity"
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, error_msgs.invalid_input
    end

    -- Initialize output structure using cached values
    local output = {
        class_uid = OCSF_CLASS.uid,
        class_name = OCSF_CLASS.name,
        category_uid = OCSF_CLASS.category_uid,
        category_name = OCSF_CLASS.category_name,
        activity_id = 1,
        type_uid = 100101,
        metadata = {
            product = {
                name = "nginx",
                vendor_name = "nginx"
            }
        }
    }

    -- Efficient request field transformation with validation
    if record.request then
        if type(record.request) == "string" then
            output.http_request = record.request
        else
            return nil, error_msgs.malformed_request
        end
    end

    -- Add enrichment data
    output.observability = {
        parser_id = "nginx_kvlog_logs-latest",
        ingestion_time = os_time() * 1000
    }

    -- Validate required fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, error_msgs.invalid_class
    end

    -- Add timestamp if not present
    if not output.time then
        output.time = os_time() * 1000
    end

    -- Optional: Add debug info in development
    if _DEBUG then
        output._debug = {
            parser_version = "1.0.0",
            processed_at = os_time()
        }
    end

    return output
end

-- Error handling wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end

-- Cache clearing function for memory optimization
function clear_cache()
    error_msgs = nil
    OCSF_CLASS = nil
    collectgarbage("collect")
end