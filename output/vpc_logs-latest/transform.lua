--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: vpc_logs-latest
  Generated: 2025-10-13T12:37:01.473480
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: vpc_logs-latest 
-- OCSF Class: Network Traffic (2001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:04:27.685196

-- Pre-declare locals for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_match = string.match
local ipv4_pattern = "^%d+%.%d+%.%d+%.%d+$"

-- Protocol number mapping table
local protocol_map = {
    ["6"] = "TCP",
    ["17"] = "UDP",
    ["1"] = "ICMP"
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure with local reference
    local output = {
        class_uid = 2001,
        class_name = "Network Traffic", 
        category_uid = 2,
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = 200101,
        metadata = {
            product = {
                name = "AWS VPC Flow Logs",
                vendor_name = "AWS"
            }
        },
        network = {},
        src_endpoint = {},
        dst_endpoint = {}
    }

    -- Validate and transform source IP
    if record.srcaddr then
        if string_match(record.srcaddr, ipv4_pattern) then
            output.src_endpoint.ip = record.srcaddr
        else
            return nil, "Invalid source IP format"
        end
    end

    -- Validate and transform destination IP
    if record.dstaddr then
        if string_match(record.dstaddr, ipv4_pattern) then
            output.dst_endpoint.ip = record.dstaddr
        else
            return nil, "Invalid destination IP format"
        end
    end

    -- Transform protocol with mapping
    if record.protocol then
        local protocol_num = tonumber(record.protocol)
        if protocol_num then
            output.network.protocol_num = protocol_num
            output.network.protocol_name = protocol_map[tostring(protocol_num)] or "OTHER"
        end
    end

    -- Transform action with validation
    if record.action then
        local action = string.upper(record.action)
        if action == "ACCEPT" or action == "REJECT" then
            output.network.action = action
        else
            output.network.action = "UNKNOWN"
        end
    end

    -- Transform traffic metrics
    if record.bytes then
        output.network.bytes = tonumber(record.bytes) or 0
    end
    if record.packets then
        output.network.packets = tonumber(record.packets) or 0
    end

    -- Transform timestamps
    if record.start and record.end then
        local start_time = tonumber(record.start)
        local end_time = tonumber(record.end)
        if start_time and end_time then
            output.time = start_time * 1000 -- Convert to milliseconds
            output.duration = end_time - start_time
        end
    else
        output.time = os_time() * 1000
    end

    -- Port number transformation
    if record.srcport then
        output.src_endpoint.port = tonumber(record.srcport)
    end
    if record.dstport then
        output.dst_endpoint.port = tonumber(record.dstport)
    end

    -- Final validation
    if not (output.src_endpoint.ip and output.dst_endpoint.ip) then
        return nil, "Missing required IP addresses"
    end

    return output
end

-- Error wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, "Transform error: " .. tostring(result)
    end
    return result
end