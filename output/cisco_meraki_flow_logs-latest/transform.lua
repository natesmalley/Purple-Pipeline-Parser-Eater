-- SentinelOne Parser: cisco_meraki_flow_logs-latest 
-- OCSF Class: Network Activity (4001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:55:23.137896

-- Pre-compile patterns for performance
local PATTERNS = {
    ip = "^%d+%.%d+%.%d+%.%d+$",
    port = "^%d+$",
    protocol = "^(tcp|udp|icmp)$",
    mac = "^%x%x:%x%x:%x%x:%x%x:%x%x:%x%x$"
}

-- Cached string formats
local FMT = {
    endpoint = "%s:%s",
    error = "Field validation failed: %s"
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize output structure with local vars for performance
    local output = {
        -- OCSF required fields
        class_uid = 4001,
        class_name = "Network Activity", 
        category_uid = 4,
        category_name = "Network Activity",
        type_uid = 400101,
        activity_id = 1,
        activity_name = "Traffic",

        -- Initialize nested structures
        src_endpoint = {},
        dst_endpoint = {},
        connection_info = {},
        metadata = {
            version = "1.0.0",
            product = {
                vendor_name = "Cisco",
                name = "Meraki",
                feature = {
                    name = "Flow Logs"
                }
            }
        }
    }

    -- Optimized field transformations using local vars
    local src_ip = record.src_ip
    local dst_ip = record.dst_ip
    local protocol = record.protocol
    local timestamp = record.timestamp
    local src_port = record.src_port
    local dst_port = record.dst_port
    local src_mac = record.src_mac

    -- Validate and transform IP addresses
    if src_ip and string.match(src_ip, PATTERNS.ip) then
        output.src_endpoint.ip = src_ip
    end
    
    if dst_ip and string.match(dst_ip, PATTERNS.ip) then
        output.dst_endpoint.ip = dst_ip
    end

    -- Transform ports with validation
    if src_port and string.match(src_port, PATTERNS.port) then
        output.src_endpoint.port = tonumber(src_port)
    end

    if dst_port and string.match(dst_port, PATTERNS.port) then
        output.dst_endpoint.port = tonumber(dst_port)
    end

    -- Protocol transformation with validation
    if protocol and string.match(protocol, PATTERNS.protocol) then
        output.connection_info.protocol_name = protocol
    end

    -- MAC address transformation
    if src_mac and string.match(src_mac, PATTERNS.mac) then
        output.src_endpoint.mac = src_mac
    end

    -- Timestamp handling with fallback
    if timestamp then
        output.time = tonumber(timestamp) * 1000 -- Convert to milliseconds
    else
        output.time = os.time() * 1000
    end

    -- Connection status mapping
    if record.connection_status then
        local status = record.connection_status:lower()
        output.connection_info.boundary = status
        output.status_id = (status == "start" or status == "allowed") and 1 or 2
    end

    -- Generate observables array for correlation
    if src_ip and dst_ip then
        output.observables = {
            {
                name = "src_ip",
                type = "IP Address", 
                value = src_ip
            },
            {
                name = "dst_ip",
                type = "IP Address",
                value = dst_ip
            }
        }
    end

    -- Final validation of required fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Missing required OCSF fields"
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