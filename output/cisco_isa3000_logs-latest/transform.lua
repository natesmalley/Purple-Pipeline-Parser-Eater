-- SentinelOne Parser: cisco_isa3000_logs-latest 
-- OCSF Class: Security Control (2001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:54:11.641572

-- Pre-compile patterns for performance
local patterns = {
    ip = "^%d+%.%d+%.%d+%.%d+$",
    port = "^%d+$"
}

-- Severity mapping table
local severity_map = {
    CRITICAL = 5,
    HIGH = 4, 
    WARNING = 3,
    NOTICE = 2,
    INFO = 1
}

-- Action mapping table
local action_map = {
    DENY = 2,
    DROP = 2,
    ALLOW = 1,
    ALERT = 99
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local variables
    local output = {
        -- Core OCSF fields
        class_uid = 2001,
        class_name = "Security Control",
        category_uid = 2,
        category_name = "Findings",
        type_uid = 200101,
        activity_id = 1,
        activity_name = "Security Alert",

        -- Initialize nested structures
        device = {},
        src_endpoint = {},
        dst_endpoint = {},
        connection_info = {},
        metadata = {}
    }

    -- Timestamp handling with validation
    if record.timestamp then
        output.time = record.timestamp
    else
        output.time = os.time() * 1000
    end

    -- Device information
    if record.hostname then
        output.device.hostname = record.hostname
    end
    if record.device_ip and string.match(record.device_ip, patterns.ip) then
        output.device.ip = record.device_ip
    end

    -- Source endpoint processing
    if record.source_ip and string.match(record.source_ip, patterns.ip) then
        output.src_endpoint.ip = record.source_ip
        if record.source_port and string.match(record.source_port, patterns.port) then
            output.src_endpoint.port = tonumber(record.source_port)
        end
        if record.zone_from then
            output.src_endpoint.zone_uid = record.zone_from
        end
    end

    -- Destination endpoint processing
    if record.destination_ip and string.match(record.destination_ip, patterns.ip) then
        output.dst_endpoint.ip = record.destination_ip
        if record.destination_port and string.match(record.destination_port, patterns.port) then
            output.dst_endpoint.port = tonumber(record.destination_port)
        end
        if record.zone_to then
            output.dst_endpoint.zone_uid = record.zone_to
        end
    end

    -- Protocol and connection info
    if record.protocol then
        output.connection_info.protocol_name = record.protocol
    end

    -- Action/disposition mapping
    if record.action then
        output.disposition = record.action
        output.status_id = action_map[record.action] or 0
    end

    -- Severity mapping
    if record.severity then
        output.severity_id = severity_map[record.severity] or 1
    end

    -- Message ID handling
    if record.message_id then
        output.metadata.uid = record.message_id
    end

    -- Modbus-specific handling
    if record.event_type == "MODBUS" then
        output.class_uid = 4001
        output.class_name = "Network Activity"
        output.category_uid = 4
        output.type_uid = 400199
        output.activity_id = 99
        
        if record.modbus_function_code then
            output.metadata.product = {
                feature = {
                    uid = tonumber(record.modbus_function_code)
                }
            }
        end
        
        if record.modbus_function_name then
            output.type_name = record.modbus_function_name
        end
    end

    -- Generate observables array for IPs
    if record.source_ip and record.destination_ip then
        output.observables = {
            {
                name = "src_ip",
                type = "IP Address", 
                value = record.source_ip
            },
            {
                name = "dst_ip",
                type = "IP Address",
                value = record.destination_ip
            }
        }
    end

    -- Final validation
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    return output
end