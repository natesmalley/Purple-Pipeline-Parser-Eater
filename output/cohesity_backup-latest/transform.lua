-- SentinelOne Parser: cohesity_backup-latest 
-- OCSF Class: System Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:57:07.097402

-- Pre-compile patterns for performance
local patterns = {
    timestamp = "^(%d%d%d%d%-%d%d%-%d%dT%d%d:%d%d:%d%dZ)",
    log = "Cohesity%s+runId=\"([^\"]+)\"%s+jobName=\"([^\"]+)\"%s+objectName=\"([^\"]+)\"%s+status=\"([^\"]+)\".-duration=\"([^\"]*)\"-?bytesProtected=([^%s]*)-?throughput=\"([^\"]*)\"-?error=\"([^\"]*)\"-?initiatedBy=\"([^\"]*)\"%s+message=\"([^\"]+)\""
}

-- Status to activity_id mapping
local status_map = {
    STARTED = 1,
    SUCCESS = 2, 
    FAILED = 3,
    WARNING = 4
}

-- Status to severity mapping
local severity_map = {
    STARTED = {id = 1, name = "Informational"},
    SUCCESS = {id = 1, name = "Informational"},
    WARNING = {id = 2, name = "Medium"},
    FAILED = {id = 3, name = "High"}
}

function transform(record)
    -- Input validation
    if not record or type(record) ~= "table" or not record.raw then
        return nil, "Invalid input record"
    end

    -- Initialize output with required OCSF fields
    local output = {
        class_uid = 1001,
        class_name = "System Activity",
        category_uid = 1,
        category_name = "System",
        metadata = {},
        job = {},
        resource = {},
        traffic = {},
        actor = {
            user = {}
        }
    }

    -- Extract timestamp and log components
    local timestamp, run_id, job_name, object_name, status, duration, 
          bytes, throughput, error, initiated_by, message = 
          string.match(record.raw, patterns.log)

    if not status then
        return nil, "Failed to parse log message"
    end

    -- Optimized field mappings
    output.metadata.correlation_uid = run_id
    output.job.name = job_name
    output.resource.name = object_name
    output.status = status
    output.duration = tonumber(duration) or 0
    output.traffic.bytes = tonumber(bytes) or 0
    output.throughput = throughput
    output.status_detail = error ~= "" and error or nil
    output.actor.user.name = initiated_by
    output.message = message

    -- Map status to activity and severity
    local activity_id = status_map[status] or 99
    output.activity_id = activity_id
    output.activity_name = activity_id == 99 and "Other" or 
                          activity_id == 1 and "Start" or "Stop"

    -- Set severity based on status
    local severity = severity_map[status] or {id = 1, name = "Informational"}
    output.severity_id = severity.id
    output.severity = severity.name

    -- Add timestamp if parsed successfully
    if timestamp then
        output.time = os.time({
            year = tonumber(timestamp:sub(1,4)),
            month = tonumber(timestamp:sub(6,7)),
            day = tonumber(timestamp:sub(9,10)),
            hour = tonumber(timestamp:sub(12,13)),
            min = tonumber(timestamp:sub(15,16)), 
            sec = tonumber(timestamp:sub(18,19))
        }) * 1000
    else
        output.time = os.time() * 1000
    end

    -- Validate required fields
    if not output.class_uid or not output.status then
        return nil, "Missing required fields"
    end

    return output
end

-- Error handling wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, "Transform error: " .. tostring(result)
    end
    return result
end