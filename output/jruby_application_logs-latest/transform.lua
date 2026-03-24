-- SentinelOne Parser: jruby_application_logs-latest 
-- OCSF Class: Application Activity (2001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:03:17.458501

-- Pre-compile patterns for performance
local TIMESTAMP_PATTERN = "^(%d%d%d%d%-%d%d%-%d%d[T%s]%d%d:%d%d:%d%d%.%d+)"
local IP_PATTERN = "^%d+%.%d+%.%d+%.%d+$"

-- Cached severity mapping for performance
local SEVERITY_MAP = {
    ERROR = 1,
    WARN = 2, 
    INFO = 3,
    DEBUG = 4
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local vars
    local output = {
        class_uid = 2001,
        class_name = "Application Activity",
        category_uid = 2,
        category_name = "Application Events",
        activity_id = 1,
        type_uid = 200101,
        metadata = {
            version = "1.0.0",
            product = {
                name = "JRuby Application",
                vendor_name = "Generic"
            }
        }
    }

    -- Timestamp processing with validation
    if record.timestamp then
        local ts = record.timestamp:match(TIMESTAMP_PATTERN)
        if ts then
            -- Convert to UNIX milliseconds
            output.time = os.time({
                year = ts:sub(1,4),
                month = ts:sub(6,7),
                day = ts:sub(9,10),
                hour = ts:sub(12,13),
                min = ts:sub(15,16),
                sec = ts:sub(18,19)
            }) * 1000
        end
    end

    -- Severity mapping with validation
    if record.severity then
        local sev = string.upper(record.severity)
        output.severity = SEVERITY_MAP[sev] or 3 -- Default to INFO
    end

    -- IP address validation and transformation
    if record.ip and record.ip:match(IP_PATTERN) then
        output.src_ip = record.ip
        output.src = {
            ip = record.ip,
            category = "ipv4"
        }
    end

    -- Correlation ID handling
    if record.correlationId then
        output.correlation_uid = record.correlationId
        -- Add to metadata for tracking
        output.metadata.correlation = {
            uid = record.correlationId
        }
    end

    -- Message handling with sanitization
    if record.message then
        -- Truncate long messages
        output.message = string.sub(record.message, 1, 32768)
    end

    -- Status code handling
    if record.status then
        local status = tonumber(record.status)
        if status then
            output.status = status
            output.status_detail = string.format("HTTP %d", status)
        end
    end

    -- Validation and cleanup
    if not output.time then
        output.time = os.time() * 1000
    end

    -- Add default severity if none present
    if not output.severity then
        output.severity = 3 -- INFO
    end

    return output
end

-- Error handler wrapper
function safe_transform(record)
    local status, result = pcall(transform, record)
    if not status then
        return nil, string.format("Transform error: %s", result)
    end
    return result
end