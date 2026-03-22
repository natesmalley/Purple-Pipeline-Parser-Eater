-- SentinelOne Parser: vcenter_logs-latest
-- OCSF Class: System Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T11:14:10.898765

-- Pre-compile patterns for timestamp matching
local timestamp_patterns = {
    "(%d%d%d%d%-%d%d%-%d+T%d%d:%d%d:%d%d%.%d+Z)",
    "(%d%d%d%d%-%d%d%-%d+T%d%d:%d%d:%d%d%.%d+[%+%-]%d%d%d%d)",
    "(%w+ %d+ %d%d:%d%d:%d%d)",
    "(%d%d/%w%w%w/%d%d%d%d:%d%d:%d%d:%d%d [%+%-]%d%d%d%d)"
}

-- Severity normalization map
local severity_map = {
    INFO = "info",
    WARNING = "warning", 
    ERROR = "error",
    CRITICAL = "critical",
    DEBUG = "debug"
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local vars for performance
    local output = {
        class_uid = 1001,
        class_name = "System Activity",
        category_uid = 1, 
        category_name = "System",
        activity_id = 1,
        type_uid = 100101,
        metadata = {
            product = {
                name = "VCenter",
                vendor = "VMware"
            },
            version = "1.0"
        }
    }

    -- Initialize actor table if user exists
    if record.user then
        output.actor = {
            user = {
                name = record.user
            }
        }
    end

    -- Timestamp processing with pattern matching
    local timestamp = record.createdTime
    if timestamp then
        for _, pattern in ipairs(timestamp_patterns) do
            local ts = string.match(timestamp, pattern)
            if ts then
                -- Convert to UNIX milliseconds and store
                output.time = os.time({
                    year = string.sub(ts,1,4),
                    month = string.sub(ts,6,7),
                    day = string.sub(ts,9,10),
                    hour = string.sub(ts,12,13),
                    min = string.sub(ts,15,16),
                    sec = string.sub(ts,18,19)
                }) * 1000
                break
            end
        end
    end

    -- Normalize severity if present
    if record.severity then
        local sev = string.upper(record.severity)
        output.severity = severity_map[sev] or "unknown"
    end

    -- Add message details if available
    if record.desc then
        output.message = record.desc
    end

    -- Add component info
    if record.component then
        output.component = {
            name = record.component,
            id = record.component_id
        }
    end

    -- Add source info if host exists
    if record.host then
        output.src = {
            hostname = record.host
        }
    end

    -- Validation of required fields
    if not output.time then
        output.time = os.time() * 1000 -- Default to current time
    end

    if not output.severity then
        output.severity = "unknown"
    end

    -- Final validation
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    return output
end

-- Error handler wrapper
function safe_transform(record)
    local status, result = pcall(transform, record)
    if status then
        return result
    else
        return nil, "Transform error: " .. tostring(result)
    end
end