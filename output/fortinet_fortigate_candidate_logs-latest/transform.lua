-- SentinelOne Parser: fortinet_fortigate_candidate_logs-latest 
-- OCSF Class: Network Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:59:57.625008

-- Pre-compile patterns for performance
local DATETIME_PATTERN = "^date=(%d+-%d+-%d+) time=(%d+:%d+:%d+)"
local IP_PATTERN = "^%d+%.%d+%.%d+%.%d+$"

-- Cached reference to frequently used functions
local type = type
local tonumber = tonumber
local format = string.format
local match = string.match
local time = os.time

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local references
    local output = {
        metadata = {
            version = "1.0.0",
            class_uid = 1001,
            class_name = "Network Activity",
            category_uid = 1, 
            category_name = "Network & Systems Activity"
        },
        event = {
            network = {},
            source = {},
            target = {}
        },
        src_endpoint = {},
        dst_endpoint = {}
    }

    -- Local reference to fortinet data for performance
    local fortinet = record.fortinet
    if not fortinet then
        return nil, "Missing fortinet data"
    end

    -- Efficient field mapping with validation
    local function safeMap(src, dest, validator)
        if src and (not validator or validator(src)) then
            return src
        end
        return nil
    end

    -- IP address validation
    local function isValidIP(ip)
        return ip and match(ip, IP_PATTERN) ~= nil
    end

    -- Map network connection status
    output.event.network.connectionStatus = safeMap(fortinet.action, output.event.network.connectionStatus)
    
    -- Map source IP with validation
    local srcIP = safeMap(fortinet.srcip, nil, isValidIP)
    if srcIP then
        output.src_endpoint.ip = srcIP
        output.event.source.ip = srcIP
    end

    -- Map destination IP with validation  
    local dstIP = safeMap(fortinet.dstip, nil, isValidIP)
    if dstIP then
        output.dst_endpoint.ip = dstIP
        output.event.target.ip = dstIP
        output.dst.ipaddress = dstIP
    end

    -- Map additional network fields
    output.event.network.direction = fortinet.subtype
    output.event.network.protocolName = fortinet.service

    -- Map port numbers with validation
    local srcPort = tonumber(fortinet.srcport)
    if srcPort and srcPort > 0 and srcPort < 65536 then
        output.src_endpoint.port = srcPort
    end

    local dstPort = tonumber(fortinet.dstport) 
    if dstPort and dstPort > 0 and dstPort < 65536 then
        output.dst_endpoint.port = dstPort
    end

    -- Map MAC addresses
    if fortinet.srcmac then
        output.src_endpoint.mac = fortinet.srcmac
    end

    -- Timestamp handling
    if record.timestamp then
        output.time = record.timestamp
    else
        output.time = time() * 1000 -- Convert to milliseconds
    end

    -- Final validation
    if not output.metadata.class_uid then
        return nil, "Missing required class_uid"
    end

    return output
end

-- Error handler wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, format("Transform error: %s", result)
    end
    return result
end