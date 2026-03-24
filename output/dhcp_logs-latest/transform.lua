-- SentinelOne Parser: dhcp_logs-latest
-- OCSF Class: Network Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:58:42.583103

-- Pre-compile patterns for performance
local ipv4_pattern = "^%d+%.%d+%.%d+%.%d+$"
local ipv6_pattern = "^[%x:]+$"
local mac_pattern = "^%x%x[:-]%x%x[:-]%x%x[:-]%x%x[:-]%x%x[:-]%x%x$"

-- Cached reference to string functions
local format = string.format
local match = string.match

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local references
    local output = {
        class_uid = 1001,
        class_name = "Network Activity", 
        category_uid = 1,
        category_name = "Network",
        activity_id = 1,
        type_uid = 100101,
        src_endpoint = {},
        metadata = {
            product = {
                name = "DHCP Server",
                vendor_name = "Generic"
            },
            version = "1.0"
        }
    }

    -- Local reference for src_endpoint for performance
    local src_endpoint = output.src_endpoint

    -- Timestamp handling with validation
    if record.timestamp then
        local ts = tonumber(record.timestamp)
        if ts then
            output.time = ts * 1000 -- Convert to milliseconds
        else
            output.time = os.time() * 1000
        end
    else
        output.time = os.time() * 1000
    end

    -- IP Address validation and transformation
    if record.ipAddress then
        local ip = record.ipAddress
        if match(ip, ipv4_pattern) or match(ip, ipv6_pattern) then
            src_endpoint.ip = ip
            -- Set IP type
            src_endpoint.ip_type = match(ip, ":") and "ipv6" or "ipv4"
        end
    end

    -- Hostname transformation with sanitization
    if record.hostname then
        local hostname = record.hostname:match("^[%w%.%-]+$")
        if hostname then
            src_endpoint.hostname = hostname
        end
    end

    -- MAC address validation and normalization
    if record.macAddress then
        local mac = record.macAddress:lower():gsub("[:-]", ":")
        if match(mac, mac_pattern) then
            src_endpoint.mac = mac
        end
    end

    -- Event details enrichment
    if record.eventId then
        output.event = {
            code = tonumber(record.eventId) or 0,
            name = "DHCP_" .. (record.description or "EVENT")
        }
    end

    -- Add status information
    output.status = record.qResult or "unknown"
    
    -- Validation of required OCSF fields
    if not output.time then
        return nil, "Missing required timestamp"
    end

    -- Add observability metadata
    output.observability = {
        parser_version = "1.0",
        ingestion_time = os.time() * 1000
    }

    return output
end

-- Error wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, format("Transform error: %s", result)
    end
    return result
end