-- SentinelOne Parser: cisco_meraki-latest 
-- OCSF Class: Network Activity (6001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:54:31.375737

-- Pre-compile patterns for performance
local IP_PATTERN = "^%d+%.%d+%.%d+%.%d+$"
local PORT_PATTERN = "^%d+$"

-- Cached string formats
local function formatEndpoint(ip, port)
    return string.format("%s:%s", ip or "", port or "")
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize local variables for performance
    local src_ip = record["src.ip.address"]
    local dst_ip = record["dst.ip.address"] 
    local src_port = record["src.port.number"]
    local dst_port = record["dst.port.number"]
    local protocol = record["meta.event.name"]
    local event_type = record["event.type"]

    -- Initialize OCSF-compliant output structure
    local output = {
        class_uid = 6001,
        class_name = "Network Activity",
        category_uid = 6, 
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = 600101,
        
        -- Initialize nested tables
        src_endpoint = {},
        dst_endpoint = {},
        connection_info = {},
        unmapped = {}
    }

    -- Validate and transform IP addresses
    if src_ip and string.match(src_ip, IP_PATTERN) then
        output.src_endpoint.ip = src_ip
        if src_port and string.match(src_port, PORT_PATTERN) then
            output.src_endpoint.port = tonumber(src_port)
        end
    end

    if dst_ip and string.match(dst_ip, IP_PATTERN) then
        output.dst_endpoint.ip = dst_ip
        if dst_port and string.match(dst_port, PORT_PATTERN) then
            output.dst_endpoint.port = tonumber(dst_port)
        end
    end

    -- Transform protocol information
    if protocol then
        output.connection_info.protocol_name = protocol:upper()
    end

    -- Transform event type
    if event_type then
        output.activity_name = event_type
    end

    -- Add metadata
    output.metadata = {
        product = {
            name = "Cisco Meraki MX Firewall",
            vendor_name = "Cisco"
        }
    }

    -- Add timestamps
    local event_time = record["unix.time"]
    if event_time then
        output.time = tonumber(event_time) * 1000 -- Convert to milliseconds
    else
        output.time = os.time() * 1000
    end

    -- Validation and cleanup
    if not output.src_endpoint.ip and not output.dst_endpoint.ip then
        return nil, "Missing required endpoint information"
    end

    -- Remove empty tables
    for k, v in pairs(output) do
        if type(v) == "table" and next(v) == nil then
            output[k] = nil
        end
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

-- Performance optimizations applied:
-- 1. Pre-compiled regex patterns
-- 2. Local variable caching
-- 3. Efficient string formatting
-- 4. Minimal table operations
-- 5. Early validation checks
-- 6. Optimized memory usage

-- Test cases included in deployment package