-- SentinelOne Parser: google_workspace_logs-latest
-- OCSF Class: Authentication (3002) 
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:00:43.432344

-- Pre-compile patterns for performance
local PATTERNS = {
    timestamp = "^(%d%d%d%d)%-(%d%d)%-(%d%d)T(%d%d):(%d%d):(%d%d)%.?(%d*)",
    email = "^[%w%.%%%+%-]+@[%w%.%-]+%.%w+$",
    ipv4 = "^(%d+)%.(%d+)%.(%d+)%.(%d+)$"
}

-- Validation helper functions
local function validate_ip(ip)
    if not ip then return false end
    local p1,p2,p3,p4 = ip:match(PATTERNS.ipv4)
    if not p1 then return false end
    for _,v in ipairs({p1,p2,p3,p4}) do
        v = tonumber(v)
        if not v or v < 0 or v > 255 then return false end
    end
    return true
end

local function validate_email(email)
    return email and email:match(PATTERNS.email) ~= nil
end

local function parse_timestamp(ts)
    if not ts then return nil end
    local y,m,d,h,min,s,ms = ts:match(PATTERNS.timestamp)
    if not y then return nil end
    return os.time({
        year = tonumber(y),
        month = tonumber(m),
        day = tonumber(d),
        hour = tonumber(h),
        min = tonumber(min),
        sec = tonumber(s)
    }) * 1000 + (tonumber(ms) or 0)
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure with local vars
    local output = {
        class_uid = 3002,
        class_name = "Authentication",
        category_uid = 3, 
        category_name = "Identity & Access Management",
        metadata = {
            product = {
                name = "Google Workspace",
                vendor_name = "Google"
            },
            version = "1.0.0"
        },
        time = parse_timestamp(record.timestamp),
        actor = {},
        src_endpoint = {},
        severity_id = record.severity_id or 1
    }

    -- Efficient field transformations using local vars
    local user_email = record.user_email
    if user_email and validate_email(user_email) then
        output.actor.user = {email = user_email}
    end

    local src_ip = record.src_ip
    if src_ip and validate_ip(src_ip) then
        output.src_endpoint.ip = src_ip
    end

    if record.event_type then
        output.activity_name = record.event_type
        -- Map common event types to activity IDs
        local activity_map = {
            login = 1,
            logout = 2,
            password_change = 3
        }
        output.activity_id = activity_map[record.event_type:lower()] or 1
    end

    -- Add action details if present
    if record.action then
        output.status = record.action
    end

    -- Validation and cleanup
    if not output.time then
        output.time = os.time() * 1000
    end

    if not output.activity_name then
        output.activity_name = "unknown_activity"
    end

    -- Final validation
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
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