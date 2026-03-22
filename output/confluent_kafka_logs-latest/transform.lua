-- SentinelOne Parser: confluent_kafka_logs-latest 
-- OCSF Class: System Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:57:08.103553

-- Pre-compile patterns for better performance
local TIMESTAMP_PATTERN = "^%d%d%d%d%-%d%d%-%d%d[T%s]%d%d:%d%d:%d%d"
local IP_PATTERN = "^%d+%.%d+%.%d+%.%d+$"

-- Severity mapping table
local SEVERITY_MAP = {
    DEBUG = 1,
    INFO = 2, 
    WARN = 3,
    ERROR = 4,
    FATAL = 5
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local vars
    local output = {
        class_uid = 1001,
        class_name = "System Activity",
        category_uid = 1,
        category_name = "System",
        activity_id = 1,
        type_uid = 100101,
        metadata = {
            version = "1.0.0",
            product = {
                name = "Confluent Kafka",
                vendor_name = "Confluent"
            }
        }
    }

    -- Timestamp transformation with validation
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
        output.severity = SEVERITY_MAP[sev] or 2 -- Default to INFO if unknown
    end

    -- IP address validation and transformation
    if record.ip then
        if record.ip:match(IP_PATTERN) then
            output.src_endpoint = {
                ip = record.ip,
                type = "ipv4"
            }
        end
    end

    -- Message/details field transformation
    if record.details then
        output.message = string.format("%.8192s", record.details) -- Truncate to 8KB
    end

    -- Enrichment and cleanup
    output.observability = {
        id = string.format("kafka_%s", os.time()),
        state = "success"
    }

    -- Final validation
    if not output.time then
        output.time = os.time() * 1000 -- Default to current time
    end

    if not output.message then
        output.message = "No message content"
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

-- Batch processing optimization
function transform_batch(records)
    local results = {}
    local errors = {}
    
    for i, record in ipairs(records) do
        local result, err = safe_transform(record)
        if result then
            results[#results + 1] = result
        else
            errors[#errors + 1] = {index = i, error = err}
        end
    end
    
    return results, errors
end