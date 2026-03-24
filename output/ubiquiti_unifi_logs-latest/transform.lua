--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: ubiquiti_unifi_logs-latest
  Generated: 2025-10-13T12:34:53.620708
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: ubiquiti_unifi_logs-latest 
-- OCSF Class: Network Connection (4001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:04:15.237277

-- Pre-compile patterns for better performance
local patterns = {
    timestamp = "^(%d%d%d%d%-%d%d%-%d%dT%d%d:%d%d:%d%d%.?%d*[%+%-]%d%d:%d%d)",
    mac = "([0-9a-fA-F][0-9a-fA-F][:%-][0-9a-fA-F][0-9a-fA-F][:%-][0-9a-fA-F][0-9a-fA-F][:%-][0-9a-fA-F][0-9a-fA-F][:%-][0-9a-fA-F][0-9a-fA-F][:%-][0-9a-fA-F][0-9a-fA-F])",
    ipv4 = "(%d+%.%d+%.%d+%.%d+)"
}

-- Cached functions for performance
local string_match = string.match
local os_time = os.time
local type = type

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure with local vars
    local output = {
        class_uid = 4001,
        class_name = "Network Connection",
        category_uid = 4,
        category_name = "Network Activity",
        metadata = {
            product = {
                name = "UniFi Network Controller",
                vendor_name = "Ubiquiti Inc."
            },
            version = "1.0.0"
        },
        time = nil,
        device = {},
        src = {},
        dst = {}
    }

    -- Extract and validate timestamp
    if record.timestamp then
        local ts = string_match(record.timestamp, patterns.timestamp)
        if ts then
            -- Convert timestamp to UNIX milliseconds
            -- Note: Simplified conversion for example
            output.time = os_time() * 1000
        end
    end

    -- Extract client MAC address
    if record.client_mac then
        local mac = string_match(record.client_mac, patterns.mac)
        if mac then
            output.device.mac = mac:upper() -- Normalize MAC to uppercase
        end
    end

    -- Extract client IP
    if record.client_ip then
        local ip = string_match(record.client_ip, patterns.ipv4)
        if ip then
            output.device.ip = ip
        end
    end

    -- Handle authentication status if present
    if record.auth_status then
        output.status = record.auth_status
        output.status_code = tonumber(record.status_code) or 0
    end

    -- Add connection details for AP events
    if record.ap_name then
        output.src.hostname = record.ap_name
    end

    -- Validate required OCSF fields
    if not output.time then
        output.time = os_time() * 1000
    end

    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
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