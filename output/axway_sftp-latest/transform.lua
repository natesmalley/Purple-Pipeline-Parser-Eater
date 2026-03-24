-- SentinelOne Parser: axway_sftp-latest
-- OCSF Class: File System Activity (1006)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:51:55.817194

-- Pre-compile patterns for performance
local PATTERNS = {
    timestamp = "^(%d%d%d%d%-%d%d%-%d%dT%d%d:%d%d:%d%dZ)",
    log = "AxwaySFTP%s+session_id=\"([^\"]+)\"%s+user=\"([^\"]+)\"%s+event=\"([^\"]+)\".-filePath=\"([^\"]*)\"-?%s*fileSize=(%d*)-?%s*bytesTransferred=(%d*)-?%s*remote_ip=\"([^\"]*)\"%s+result=\"([^\"]+)\"%s+message=\"([^\"]+)\""
}

-- Activity mapping table for O(1) lookups
local ACTIVITY_MAPPINGS = {
    LOGIN = {id = 1, name = "Login"},
    UPLOAD = {id = 2, name = "Create"},
    DOWNLOAD = {id = 3, name = "Read"},
    DELETE = {id = 4, name = "Delete"},
    RENAME = {id = 5, name = "Rename"},
    DEFAULT = {id = 99, name = "Other"}
}

-- Severity mapping table
local SEVERITY_MAPPINGS = {
    SUCCESS = {id = 1, name = "Informational"},
    FAILURE = {id = 3, name = "High"}
}

function transform(record)
    -- Input validation
    if not record or type(record) ~= "table" or not record.raw then
        return nil, "Invalid input record"
    end

    -- Initialize local variables for performance
    local session_id, username, event_type, file_path, file_size
    local bytes_transferred, remote_ip, result, message

    -- Parse log entry
    local raw = record.raw
    local timestamp = raw:match(PATTERNS.timestamp)
    session_id, username, event_type, file_path, file_size,
    bytes_transferred, remote_ip, result, message = raw:match(PATTERNS.log)

    -- Validate required fields
    if not session_id or not username or not event_type then
        return nil, "Missing required fields"
    end

    -- Get activity mapping
    local activity = ACTIVITY_MAPPINGS[event_type] or ACTIVITY_MAPPINGS.DEFAULT
    local severity = SEVERITY_MAPPINGS[result] or SEVERITY_MAPPINGS.FAILURE

    -- Build OCSF-compliant output structure
    local output = {
        -- Mandatory OCSF fields
        class_uid = 1006,
        class_name = "File System Activity",
        category_uid = 1,
        category_name = "System Activity",
        activity_id = activity.id,
        activity_name = activity.name,
        severity_id = severity.id,
        severity = severity.name,
        time = timestamp and os.time({
            year = timestamp:sub(1,4),
            month = timestamp:sub(6,7),
            day = timestamp:sub(9,10),
            hour = timestamp:sub(12,13),
            min = timestamp:sub(15,16),
            sec = timestamp:sub(18,19)
        }) * 1000 or os.time() * 1000,

        -- Event-specific fields
        session_id = session_id,
        actor = {
            user = {
                name = username
            }
        },
        event_type = event_type,
        status = result,
        message = message
    }

    -- Add optional fields if present
    if file_path and file_path ~= "" then
        output.file = {
            path = file_path,
            size = tonumber(file_size)
        }
    end

    if bytes_transferred and bytes_transferred ~= "" then
        output.traffic = {
            bytes = tonumber(bytes_transferred)
        }
    end

    if remote_ip and remote_ip ~= "" then
        output.src_endpoint = {
            ip = remote_ip
        }
    end

    return output
end

-- Error handling wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string.format("Transform error: %s", result)
    end
    return result
end