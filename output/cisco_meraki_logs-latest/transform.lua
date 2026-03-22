-- SentinelOne Parser: cisco_meraki_logs-latest 
-- OCSF Class: Network Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:55:25.389031

-- Pre-compile patterns for performance
local IP_PATTERN = "^%d+%.%d+%.%d+%.%d+$"
local PORT_PATTERN = "^%d+$"

-- Cache common string operations
local format = string.format
local match = string.match
local type = type

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local vars for performance
    local output = {
        class_uid = 1001,
        class_name = "Network Activity", 
        category_uid = 1,
        category_name = "Network & Systems Activity",
        activity_id = 1,
        type_uid = 100101,
        metadata = {
            product = {
                name = "Cisco Meraki MX Firewall",
                vendor = "Cisco"
            }
        },
        src_endpoint = {},
        dst_endpoint = {},
        connection_info = {}
    }

    -- Optimized field transformations using local vars
    local src_ip = record["src.ip.address"]
    local dst_ip = record["dst.ip.address"]
    local protocol = record["meta.event.name"]
    
    -- Validate and transform source IP
    if src_ip and match(src_ip, IP_PATTERN) then
        output.src_endpoint.ip = src_ip
    end

    -- Validate and transform destination IP 
    if dst_ip and match(dst_ip, IP_PATTERN) then
        output.dst_endpoint.ip = dst_ip
    end

    -- Transform protocol with validation
    if protocol then
        output.connection_info.protocol_name = protocol
    end

    -- Port number transformations with validation
    local src_port = record["src.port.number"]
    local dst_port = record["dst.port.number"]
    
    if src_port and match(src_port, PORT_PATTERN) then
        output.src_endpoint.port = tonumber(src_port)
    end
    
    if dst_port and match(dst_port, PORT_PATTERN) then
        output.dst_endpoint.port = tonumber(dst_port)
    end

    -- Add event type if present
    if record["event.type"] then
        output.activity_name = record["event.type"]
    end

    -- Add timestamp handling
    local unix_time = record["unix.time"]
    if unix_time then
        output.time = tonumber(unix_time) * 1000 -- Convert to milliseconds
    else
        output.time = os.time() * 1000
    end

    -- Validation of required OCSF fields
    if not (output.src_endpoint.ip or output.dst_endpoint.ip) then
        return nil, "Missing required IP address fields"
    end

    -- Clean empty tables for efficiency
    if next(output.src_endpoint) == nil then output.src_endpoint = nil end
    if next(output.dst_endpoint) == nil then output.dst_endpoint = nil end
    if next(output.connection_info) == nil then output.connection_info = nil end

    return output
end

-- Error handling wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, format("Transform error: %s", result)
    end
    return result
end