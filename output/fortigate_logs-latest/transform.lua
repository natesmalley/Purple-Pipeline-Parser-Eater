-- SentinelOne Parser: fortigate_logs-latest 
-- OCSF Class: Network Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:59:56.609619

-- Pre-compile patterns for better performance
local datetime_pattern = "date=(%d+-%d+-%d+) time=(%d+:%d+:%d+)"

-- Cached reference to string functions
local str_match = string.match
local str_format = string.format
local os_time = os.time

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local references
    local output = {
        class_uid = 1001,
        class_name = "Network Activity", 
        category_uid = 1,
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = 100101,
        metadata = {
            product = {
                name = "FortiGate",
                vendor = "Fortinet"
            }
        }
    }

    -- Timestamp processing with error handling
    if record.datetime then
        local date, time = str_match(record.datetime, datetime_pattern)
        if date and time then
            -- Convert to UNIX timestamp (milliseconds)
            local success, timestamp = pcall(function()
                return os_time({
                    year = str_match(date, "(%d+)"),
                    month = str_match(date, "%d+-(%d+)"),
                    day = str_match(date, "%d+-%d+-(%d+)"),
                    hour = str_match(time, "(%d+)"),
                    min = str_match(time, "%d+:(%d+)"),
                    sec = str_match(time, "%d+:%d+:(%d+)")
                }) * 1000
            end)
            
            if success then
                output.time = timestamp
            end
        end
    end

    -- Severity mapping with validation
    if record.level then
        local severity = record.level:lower()
        -- Map Fortinet severity levels to OCSF
        local severity_map = {
            emergency = 100,
            alert = 200,
            critical = 300,
            error = 400,
            warning = 500,
            notice = 600,
            info = 700,
            debug = 800
        }
        output.severity = severity_map[severity] or 0
    end

    -- Additional field mappings
    if record.subtype then
        output.activity_name = record.subtype
    end
    
    if record.srcip then
        output.src_endpoint = {
            ip = record.srcip,
            port = tonumber(record.srcport)
        }
    end

    if record.dstip then
        output.dst_endpoint = {
            ip = record.dstip,
            port = tonumber(record.dstport)
        }
    end

    -- Validation of required fields
    if not output.time then
        output.time = os_time() * 1000
    end

    if not output.severity then
        output.severity = 0 -- Default severity
    end

    -- Final validation
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    return output
end

-- Error wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, str_format("Transform error: %s", result)
    end
    return result
end