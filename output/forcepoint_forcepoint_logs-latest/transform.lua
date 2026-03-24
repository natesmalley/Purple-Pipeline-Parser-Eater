-- SentinelOne Parser: forcepoint_forcepoint_logs-latest 
-- OCSF Class: Network Activity (4001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:59:36.419629

-- Pre-compile patterns for performance
local IP_PATTERN = "^%d+%.%d+%.%d+%.%d+$"
local PORT_PATTERN = "^%d+$"

-- Cached references for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_match = string.match

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize output structure with nested tables to avoid nil errors
    local output = {
        metadata = {
            version = "1.0.0",
            product = {
                vendor_name = "Forcepoint",
                name = "Forcepoint Firewall"
            }
        },
        class_uid = 4001,
        class_name = "Network Activity", 
        category_uid = 4,
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = 400101,
        src = {},
        dst = {}
    }

    -- Optimized field transformations using local references
    local src_ip = record.src
    if src_ip and string_match(src_ip, IP_PATTERN) then
        output.src.ip = {address = src_ip}
    end

    local src_port = record.spt
    if src_port then
        local port_num = tonumber(src_port)
        if port_num and port_num > 0 and port_num < 65536 then
            output.src.port = {number = port_num}
        end
    end

    local dst_ip = record.dst  
    if dst_ip and string_match(dst_ip, IP_PATTERN) then
        output.dst.ip = {address = dst_ip}
    end

    local dst_port = record.dpt
    if dst_port then
        local port_num = tonumber(dst_port)
        if port_num and port_num > 0 and port_num < 65536 then
            output.dst.port = {number = port_num}
        end
    end

    -- Timestamp handling
    local event_time = record.timestamp or (os_time() * 1000)
    output.time = event_time

    -- Validation of required fields
    if not (output.src.ip or output.dst.ip) then
        return nil, "Missing required source or destination IP"
    end

    -- Optional enrichments
    if record.protocol then
        output.network = {protocol = record.protocol}
    end

    -- Add observation metadata
    output.observables = {
        {
            time = event_time,
            type = "network_flow",
            value = string.format("%s:%s->%s:%s",
                output.src.ip.address or "",
                (output.src.port and output.src.port.number) or "",
                output.dst.ip.address or "",
                (output.dst.port and output.dst.port.number) or ""
            )
        }
    }

    return output
end

-- Error handler wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, "Transform error: " .. tostring(result)
    end
    return result
end