-- SentinelOne Parser: cisco_firewall-latest
-- OCSF Class: Network Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:53:24.137410

-- Pre-compile patterns for performance
local ipv4_pattern = "^(%d+%.%d+%.%d+%.%d+)$"
local ipv6_pattern = "^([a-fA-F0-9:]+)$"
local timestamp_pattern = "^(%w+)%s+(%d+)%s+(%d+)%s+(%d+):(%d+):(%d+)$"

-- Cache common string operations
local format = string.format
local match = string.match
local time = os.time

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
        metadata = {
            product = {
                name = "Cisco Firewall",
                vendor_name = "Cisco"
            }
        },
        network = {},
        source = {},
        destination = {}
    }

    -- Timestamp transformation with validation
    if record.timestamp then
        local mon, day, year, hour, min, sec = match(record.timestamp, timestamp_pattern)
        if mon and day and year and hour and min and sec then
            output.time = format("%s-%s-%sT%s:%s:%sZ", year, mon, day, hour, min, sec)
        else
            output.time = time() * 1000 -- Fallback to current time
        end
    end

    -- Protocol transformation with validation
    if record.protocol then
        local proto = string.lower(record.protocol)
        if proto == "tcp" or proto == "udp" or proto == "icmp" then
            output.network.protocol = proto
        end
    end

    -- IP address transformations with validation
    if record.ip1 then
        if match(record.ip1, ipv4_pattern) or match(record.ip1, ipv6_pattern) then
            output.source.ip = record.ip1
            if record.port1 then
                output.source.port = tonumber(record.port1)
            end
        end
    end

    if record.ip2 then
        if match(record.ip2, ipv4_pattern) or match(record.ip2, ipv6_pattern) then
            output.destination.ip = record.ip2
            if record.port2 then
                output.destination.port = tonumber(record.port2)
            end
        end
    end

    -- Connection details
    if record.connectionId then
        output.network.connection_id = tonumber(record.connectionId)
    end

    -- Direction mapping
    if record.direction then
        local dir = string.lower(record.direction)
        if dir == "inbound" then
            output.network.direction = "Inbound"
        elseif dir == "outbound" then
            output.network.direction = "Outbound"
        end
    end

    -- Validation of required OCSF fields
    if not output.time then
        output.time = time() * 1000
    end

    if not (output.source.ip or output.destination.ip) then
        return nil, "Missing required IP address fields"
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