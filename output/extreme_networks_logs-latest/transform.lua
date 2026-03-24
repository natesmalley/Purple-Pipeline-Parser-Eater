-- SentinelOne Parser: extreme_networks_logs-latest 
-- OCSF Class: Network Activity (4002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:59:03.786955

-- Pre-compile regex patterns for performance
local timestamp_pattern = "^(%d%d%d%d%-%d%d%-%d%d[T ]%d%d:%d%d:%d%d)"
local mac_pattern = "([0-9a-fA-F][0-9a-fA-F][:-]){5}[0-9a-fA-F][0-9a-fA-F]"

-- Cached reference to frequently used functions
local type = type
local tonumber = tonumber
local os_time = os.time
local string_match = string.match
local string_format = string.format

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local references
    local output = {
        -- Required OCSF fields
        class_uid = 4002,
        class_name = "Network Activity", 
        category_uid = 4,
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = 400201,
        
        -- Nested structures
        device = {},
        network = {},
        metadata = {
            product = {
                name = "Extreme Networks Switch",
                vendor_name = "Extreme Networks"
            },
            version = "1.0.0"
        }
    }

    -- Timestamp handling with validation
    local timestamp = record.timestamp
    if timestamp then
        local parsed_ts = string_match(timestamp, timestamp_pattern)
        if parsed_ts then
            output.time = parsed_ts
        else
            output.time = os_time() * 1000
        end
    else
        output.time = os_time() * 1000
    end

    -- Efficient field mappings using local references
    local device = output.device
    local network = output.network

    -- Hostname mapping with validation
    if record.hostname and type(record.hostname) == "string" then
        device.hostname = record.hostname
    end

    -- MAC address handling with pattern validation
    if record.mac and type(record.mac) == "string" then
        if string_match(record.mac, mac_pattern) then
            device.mac = record.mac:lower() -- Normalize MAC format
        end
    end

    -- Port mapping with validation
    if record.port and type(record.port) == "string" then
        network.interface = {
            name = record.port
        }
    end

    -- Additional network fields if present
    if record.vlan_id then
        network.vlan = {
            id = tonumber(record.vlan_id) or record.vlan_id,
            name = record.vlan_name
        }
    end

    -- Status field mapping if present
    if record.status then
        output.status = record.status
    end

    -- Message field with sanitization
    if record.message then
        output.message = record.message:sub(1, 1024) -- Limit message length
    end

    -- Final validation of required fields
    if not output.time or not output.class_uid then
        return nil, "Missing required OCSF fields"
    end

    return output
end

-- Error handling wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end