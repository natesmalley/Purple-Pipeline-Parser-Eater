--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: cisco_logs-latest
  Generated: 2025-10-13T11:26:00.611217
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: cisco_logs-latest
-- OCSF Class: Network Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T11:02:52.584294

-- Pre-compile patterns for performance
local ipv4_pattern = "^%d+%.%d+%.%d+%.%d+$"
local ipv6_pattern = "^%x+:%x+:.+$"

-- Cached protocol normalization map
local protocol_map = {
  tcp = "TCP",
  udp = "UDP",
  icmp = "ICMP"
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local variables
    local output = {
        class_uid = 1001,
        class_name = "Network Activity", 
        category_uid = 1,
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = 100101,
        network = {},
        src_endpoint = {},
        dst_endpoint = {},
        connection = {}
    }

    -- Efficient protocol transformation
    if record.protocol then
        local proto = string.lower(record.protocol)
        output.network.protocol = protocol_map[proto] or record.protocol
    end

    -- IP address validation and transformation
    if record.ip1 then
        local ip = record.ip1
        if string.match(ip, ipv4_pattern) or string.match(ip, ipv6_pattern) then
            output.src_endpoint.ip = ip
        end
    end

    if record.ip2 then
        local ip = record.ip2
        if string.match(ip, ipv4_pattern) or string.match(ip, ipv6_pattern) then
            output.dst_endpoint.ip = ip
        end
    end

    -- Safe numeric casting for connection ID
    if record.connectionId then
        local conn_id = tonumber(record.connectionId)
        if conn_id then
            output.connection.uid = conn_id
        end
    end

    -- Port number validation and assignment
    if record.port1 then
        local port = tonumber(record.port1)
        if port and port >= 0 and port <= 65535 then
            output.src_endpoint.port = port
        end
    end

    if record.port2 then
        local port = tonumber(record.port2)
        if port and port >= 0 and port <= 65535 then
            output.dst_endpoint.port = port
        end
    end

    -- Timestamp handling
    if record.timestamp then
        local ts = tonumber(record.timestamp)
        output.time = ts and ts * 1000 or os.time() * 1000
    else
        output.time = os.time() * 1000
    end

    -- Validation of required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    if not (output.src_endpoint.ip or output.dst_endpoint.ip) then
        return nil, "Missing required IP address fields"
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