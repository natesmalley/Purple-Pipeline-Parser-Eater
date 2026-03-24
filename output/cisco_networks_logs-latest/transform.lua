-- SentinelOne Parser: cisco_networks_logs-latest 
-- OCSF Class: Infrastructure Events (4002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:56:27.824822

-- Pre-compile patterns for performance
local timestamp_pattern = "^(%d%d%d%d%-%d%d%-%d%d[T ]%d%d:%d%d:%d%d)"
local severity_map = {
    ["EMERGENCY"] = 1,
    ["ALERT"] = 2, 
    ["CRITICAL"] = 3,
    ["ERROR"] = 4,
    ["WARNING"] = 5,
    ["NOTICE"] = 6,
    ["INFO"] = 7,
    ["DEBUG"] = 8
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local table
    local output = {
        metadata = {
            product = {
                name = "Cisco Networking",
                vendor_name = "Cisco"
            }
        },
        dataSource = {
            category = "security",
            name = "Cisco IOS",
            vendor = "Cisco"
        },
        class_uid = 4002,
        class_name = "Infrastructure Events", 
        category_uid = 4,
        category_name = "Cisco IOS",
        activity_id = 1,
        type_uid = 400201,
        device = {}
    }

    -- Optimized timestamp handling
    local timestamp = record.timestamp
    if timestamp then
        local parsed_time = os.time({
            year = tonumber(timestamp:sub(1,4)),
            month = tonumber(timestamp:sub(6,7)),
            day = tonumber(timestamp:sub(9,10)),
            hour = tonumber(timestamp:sub(12,13)),
            min = tonumber(timestamp:sub(15,16)), 
            sec = tonumber(timestamp:sub(18,19))
        })
        output.time = parsed_time * 1000 -- Convert to milliseconds
    else
        output.time = os.time() * 1000
    end

    -- Efficient field mappings using local references
    if record.device then
        output.device.name = record.device
        output.device.ip = record.device -- Preserve IP if present
    end

    if record.event_type then
        output.activity_name = record.event_type
        -- Extract activity details if available
        local activity_details = string.match(record.event_type, "^(%w+)%s*:%s*(.+)$")
        if activity_details then
            output.activity_details = activity_details
        end
    end

    -- Normalize severity with mapping
    if record.severity then
        local sev = string.upper(record.severity)
        output.severity = severity_map[sev] or 7 -- Default to INFO if unknown
    end

    -- Handle special fields for network events
    if record.interface then
        output.network = {
            interface = record.interface
        }
    end

    if record.nms_ip then
        output.src = {
            ip = record.nms_ip
        }
    end

    -- Validation and enrichment
    if record.message then
        output.message = record.message
        -- Extract additional context if available
        if string.match(record.message, "Native VLAN mismatch") then
            output.type_name = "VLAN_MISMATCH"
            output.severity = 4 -- Set to ERROR
        end
    end

    -- Final validation
    if not output.activity_name then
        output.activity_name = "UNKNOWN"
    end

    if not output.severity then
        output.severity = 7 -- Default to INFO
    end

    return output
end