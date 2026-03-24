--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: securelink_logs-latest
  Generated: 2025-10-13T12:55:29.253867
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: securelink_logs-latest 
-- OCSF Class: Account Change (3001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:30:58.940105

-- Pre-compile patterns for better performance
local patterns = {
    timestamp = "^(%d%d%d%d%-%d%d%-%d%dT%d%d:%d%d:%d%d)",
    ip = "^(%d+%.%d+%.%d+%.%d+)$"
}

-- Local helper functions for performance
local function validate_ip(ip)
    if not ip then return false end
    local parts = {ip:match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")}
    if #parts ~= 4 then return false end
    for _, v in ipairs(parts) do
        local num = tonumber(v)
        if not num or num < 0 or num > 255 then return false end
    end
    return true
end

local function parse_timestamp(ts)
    if not ts then return nil end
    local year, month, day, hour, min, sec = ts:match(patterns.timestamp)
    if not year then return nil end
    return os.time({year=year, month=month, day=day, hour=hour, min=min, sec=sec}) * 1000
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local table
    local output = {
        metadata = {
            version = "1.0.0",
            product = {
                name = "SecureLink",
                vendor_name = "Imprivata"
            }
        },
        class_uid = 3001,
        class_name = "Account Change", 
        category_uid = 3,
        category_name = "Identity & Access Management",
        severity_id = 1,
        time = parse_timestamp(record.timestamp) or (os.time() * 1000),
        src_endpoint = {},
        user = {},
        activity = {}
    }

    -- Efficient field transformations using local references
    local src_endpoint = output.src_endpoint
    local user = output.user
    local activity = output.activity

    -- Transform source IP with validation
    if record.src_ip and validate_ip(record.src_ip) then
        src_endpoint.ip = record.src_ip
    end

    -- Transform username with sanitization
    if record.user then
        user.name = string.match(record.user, "^[%w%p]+$") or record.user
    end

    -- Transform event type
    if record.event_type then
        output.activity_name = record.event_type
        -- Map common event types to activity IDs
        local event_map = {
            ["login"] = 1,
            ["logout"] = 2,
            ["access"] = 3
        }
        output.activity_id = event_map[record.event_type:lower()] or 1
    end

    -- Transform action if present
    if record.action then
        activity.status = record.action
    end

    -- Add resource details if present
    if record.resource then
        output.resource = {
            name = record.resource
        }
    end

    -- Validation of required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Missing required class_uid"
    end

    if not output.time then
        return nil, "Invalid timestamp"
    end

    -- Return transformed event
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