-- SentinelOne Parser: cisco_ise_logs-latest 
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:54:28.390317

-- Pre-compile patterns for performance
local patterns = {
    timestamp = "^(%d%d%d%d%-%d%d%-%d%dT%d%d:%d%d:%d%d)%.?%d*([%+%-]%d%d:%d%d)$",
    ipv4 = "^(%d+%.%d+%.%d+%.%d+)$",
    mac = "^([0-9a-fA-F][0-9a-fA-F][:-]){5}[0-9a-fA-F][0-9a-fA-F]$"
}

-- Local helper functions for performance
local function validate_ip(ip)
    if not ip then return nil end
    local parts = {ip:match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")}
    if #parts ~= 4 then return nil end
    for _, part in ipairs(parts) do
        local num = tonumber(part)
        if not num or num < 0 or num > 255 then return nil end
    end
    return ip
end

local function parse_timestamp(ts)
    if not ts then return nil end
    local date, offset = ts:match(patterns.timestamp)
    if not date then return nil end
    -- Convert to UNIX milliseconds - simplified for example
    return os.time({
        year = tonumber(date:sub(1,4)),
        month = tonumber(date:sub(6,7)),
        day = tonumber(date:sub(9,10)),
        hour = tonumber(date:sub(12,13)),
        min = tonumber(date:sub(15,16)), 
        sec = tonumber(date:sub(18,19))
    }) * 1000
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local table
    local output = {
        class_uid = 3002,
        class_name = "Authentication",
        category_uid = 3,
        category_name = "Identity & Access Management",
        activity_id = 1,
        type_uid = 300201,
        metadata = {
            product = {
                name = "Cisco Identity Services Engine",
                vendor_name = "Cisco"
            },
            version = "1.0.0"
        },
        time = parse_timestamp(record.timestamp),
        src = {},
        user = {},
        observer = {
            name = record.hostname,
            vendor = "Cisco",
            category = "security",
            product = {
                name = "Cisco ISE"
            }
        }
    }

    -- Efficient field transformations using local references
    local src = output.src
    local user = output.user

    -- Transform source IP with validation
    if record.ip then
        local valid_ip = validate_ip(record.ip)
        if valid_ip then
            src.ip = valid_ip
        end
    end

    -- Transform MAC address
    if record.mac and record.mac:match(patterns.mac) then
        src.mac = record.mac:upper() -- Normalize MAC case
    end

    -- Transform username with sanitization
    if record.user then
        user.name = record.user:gsub("[^%w%s@%-_%.]+", "") -- Basic sanitization
    end

    -- Add severity mapping
    if record.severity then
        output.severity = tonumber(record.severity) or 0
    end

    -- Add status based on log type
    if record.log_id then
        if record.log_id:match("Failed") then
            output.status = "FAILURE"
        elseif record.log_id:match("Passed") then
            output.status = "SUCCESS"
        end
    end

    -- Validation of required fields
    if not output.time then
        output.time = os.time() * 1000 -- Fallback to current time
    end

    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    return output
end