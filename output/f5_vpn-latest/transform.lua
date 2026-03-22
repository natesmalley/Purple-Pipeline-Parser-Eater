-- SentinelOne Parser: f5_vpn-latest
-- OCSF Class: Network Activity (3005)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:59:07.275656

-- Pre-compile patterns for performance
local ACTIVITY_PATTERNS = {
    SESSION_START = {id = 1, name = "Start", status_id = 1, status = "Success"},
    SESSION_END = {id = 2, name = "Stop", status_id = 99, status = "Other"},
    LOGIN = {id = 1, name = "Logon", status_id = 1, status = "Success"},
    LOGOUT = {id = 2, name = "Logoff", status_id = 99, status = "Other"},
    CONNECTION_FAILED = {id = 99, name = "Other", status_id = 2, status = "Failure"},
    AUTH_SUCCESS = {id = 1, name = "Success", status_id = 1, status = "Success"},
    AUTH_FAILURE = {id = 2, name = "Failure", status_id = 2, status = "Failure"}
}

-- Optimized validation function
local function validate_ip(ip)
    if not ip then return false end
    local parts = {ip:match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")}
    if #parts ~= 4 then return false end
    for _, part in ipairs(parts) do
        local n = tonumber(part)
        if not n or n < 0 or n > 255 then return false end
    end
    return true
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize output with static values for performance
    local output = {
        class_uid = 3005,
        class_name = "Network Activity", 
        category_uid = 4,
        category_name = "Network Activity",
        type_uid = 300503,
        severity_id = 1,
        severity = "Informational",
        session = {},
        src_endpoint = {},
        user = {}
    }

    -- Efficient field mapping with validation
    if record.session_id then
        output.session.uid = record.session_id
    end

    if record.user then
        output.user.name = record.user
    end

    if record.client_ip and validate_ip(record.client_ip) then
        output.src_endpoint.ip = record.client_ip
    end

    if record.device then
        output.src_endpoint.device = {name = record.device}
    end

    -- Activity mapping with cached patterns
    if record.event then
        local activity = ACTIVITY_PATTERNS[record.event]
        if activity then
            output.activity_id = activity.id
            output.activity_name = activity.name
            output.status_id = activity.status_id
            output.status = activity.status
        end
    end

    -- Timestamp handling
    if record.timestamp then
        output.time = record.timestamp
    else
        output.time = os.time() * 1000
    end

    -- Message field
    if record.message then
        output.message = record.message
    end

    -- Start time handling
    if record.start_time then
        output.start_time = record.start_time
    end

    -- Final validation
    if not output.activity_id then
        return nil, "Missing required activity mapping"
    end

    return output
end

-- Error handler wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string.format("Transform error: %s", result)
    end
    return result
end