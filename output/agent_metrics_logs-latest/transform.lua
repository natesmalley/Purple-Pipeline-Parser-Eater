-- SentinelOne Parser: agent_metrics_logs-latest
-- OCSF Class: Metric (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-16T14:56:13.135053

-- Pre-compile patterns for performance
local NUMERIC_PATTERN = "^[%-]?%d+[.]?%d*$"

-- Local helper functions for performance optimization
local function validate_number(value)
    if type(value) == "number" then return value end
    if type(value) ~= "string" then return nil end
    return value:match(NUMERIC_PATTERN) and tonumber(value) or nil
end

local function safe_copy(value)
    if type(value) == "string" then
        return value ~= "" and value or nil
    end
    return value
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure with local variables
    local output = {
        class_uid = 1001,
        class_name = "Metric",
        category_uid = 1,
        category_name = "System Activity",
        activity_id = 1,
        type_uid = 100101,
        metadata = {
            version = "1.0.0",
            product = {
                name = "agent_metrics",
                vendor_name = "generic"
            }
        }
    }

    -- Efficient field transformations using local variables
    local timestamp = safe_copy(record.timestamp)
    local monitor = safe_copy(record.monitor)
    local instance = safe_copy(record.instance)
    local metric = safe_copy(record.metric)
    local value = validate_number(record.value)

    -- Required field validations
    if not metric then
        return nil, "Missing required field: metric"
    end

    -- Optimized field assignments
    output.time = timestamp or (os.time() * 1000)
    output.monitor_name = monitor
    output.instance_uid = instance
    output.metric_name = metric
    output.metric_value = value

    -- Additional context fields
    if monitor and instance then
        output.observer = {
            name = string.format("%s-%s", monitor, instance),
            type = "metric_collector"
        }
    end

    -- Enrichment and data quality checks
    if value then
        output.metric_type = type(value) == "number" and "numeric" or "string"
        output.unit = "count" -- Default unit, can be customized based on metric
    end

    -- Add timestamp if missing
    if not output.time then
        output.time = os.time() * 1000
    end

    -- Final validation before return
    if not output.metric_name or not output.metric_value then
        return nil, "Missing required metric fields"
    end

    return output
end

-- Error handling wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string.format("Transform error: %s", result)
    end
    return result
end

-- Performance test helper
function benchmark(iterations)
    local start = os.clock()
    local sample = {
        timestamp = "2025-10-16T14:56:13.135Z",
        monitor = "system",
        instance = "prod-1",
        metric = "cpu_usage",
        value = "95.5"
    }
    
    for i = 1, iterations do
        safe_transform(sample)
    end
    
    return os.clock() - start
end