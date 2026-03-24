-- SentinelOne Parser: nginx_error_logs-latest 
-- OCSF Class: System Activity (2001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:07:18.056769

-- Pre-declare locals for performance
local type = type
local os_time = os.time
local string_format = string.format
local error_levels = {
    emerg = 1,
    alert = 2, 
    crit = 3,
    error = 4,
    warn = 5,
    notice = 6,
    info = 7,
    debug = 8
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure with local reference
    local output = {
        -- Required OCSF fields
        class_uid = 2001,
        class_name = "System Activity", 
        category_uid = 2,
        category_name = "System Activity",
        activity_id = 1,
        type_uid = 200101,
        metadata = {
            product = {
                name = "nginx",
                vendor_name = "nginx"
            },
            version = "1.0"
        }
    }

    -- Efficient error message handling
    if record.error_message then
        -- Use string.format for efficient concatenation
        output.message = string_format("%s", record.error_message)
        
        -- Extract severity if present in message
        for level, severity in pairs(error_levels) do
            if record.error_message:match(level) then
                output.severity = severity
                break
            end
        end
    end

    -- Extract timestamp if available
    if record.timestamp then
        -- Convert to UNIX milliseconds
        local ts = tonumber(record.timestamp)
        if ts then
            output.time = ts * 1000
        end
    end

    -- Add default timestamp if not set
    if not output.time then
        output.time = os_time() * 1000
    end

    -- Validation of required fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    if not output.message then
        output.message = "No error message provided"
    end

    return output
end

-- Error recovery function
local function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end

-- Optimized batch processing function
function transform_batch(records)
    if not records or type(records) ~= "table" then
        return nil, "Invalid batch input"
    end

    local results = {}
    local errors = {}
    
    for i, record in ipairs(records) do
        local result, err = safe_transform(record)
        if result then
            results[#results + 1] = result
        else
            errors[#errors + 1] = {
                index = i,
                error = err
            }
        end
    end
    
    return results, errors
end