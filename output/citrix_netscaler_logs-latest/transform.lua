-- SentinelOne Parser: citrix_netscaler_logs-latest 
-- OCSF Class: Network Activity (6001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:56:47.891291

-- Pre-compile patterns for better performance
local IP_PATTERN = "^%d+%.%d+%.%d+%.%d+$"
local NUM_PATTERN = "^%d+$"

-- Cached references for better performance
local type = type
local tonumber = tonumber
local time = os.time
local format = string.format
local match = string.match

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure with local table
    local output = {
        class_uid = 6001,
        class_name = "Network Activity", 
        category_uid = 6,
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = 600101,
        metadata = {
            version = "1.0.0",
            product = {
                name = "NetScaler",
                vendor = "Citrix"
            }
        }
    }

    -- Initialize nested tables efficiently
    local src_endpoint = {}
    local dst_endpoint = {}
    local network = {}
    local actor = {user = {}}

    -- Optimized field transformations with validation
    -- Source IP transformation
    if record.src and record.src.ip and record.src.ip.address then
        local src_ip = record.src.ip.address
        if match(src_ip, IP_PATTERN) then
            src_endpoint.ip = src_ip
        end
    end

    -- Destination IP transformation
    if record.dst and record.dst.ip and record.dst.ip.address then
        local dst_ip = record.dst.ip.address
        if match(dst_ip, IP_PATTERN) then
            dst_endpoint.ip = dst_ip
        end
    end

    -- Network bytes transformation with type casting
    if record.network_traffic and record.network_traffic.bytes_in then
        local bytes = tonumber(record.network_traffic.bytes_in)
        if bytes then
            network.bytes_in = bytes
        end
    end

    -- User transformation with sanitization
    if record.user and record.user.src_name then
        local username = record.user.src_name
        if type(username) == "string" and #username > 0 then
            actor.user.name = username
        end
    end

    -- Assign nested tables only if they contain data
    if next(src_endpoint) then output.src_endpoint = src_endpoint end
    if next(dst_endpoint) then output.dst_endpoint = dst_endpoint end
    if next(network) then output.network = network end
    if next(actor.user) then output.actor = actor end

    -- Timestamp handling
    output.time = record.timestamp and tonumber(record.timestamp) or (time() * 1000)

    -- Final validation
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid OCSF structure"
    end

    -- Add observability metadata
    output.observo_metadata = {
        parser_version = "1.0.0",
        processing_time = time()
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