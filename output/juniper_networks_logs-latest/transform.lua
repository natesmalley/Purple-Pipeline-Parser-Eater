-- SentinelOne Parser: juniper_networks_logs-latest 
-- OCSF Class: Network Activity (4002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:04:18.166578

-- Pre-compile regex patterns for better performance
local timestamp_pattern = "\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{3})?[+-]\\d{2}:\\d{2}|\\w{3}\\s+\\d{1,2}\\s+\\d{2}:\\d{2}:\\d{2}"
local ipv4_pattern = "^(%d%d?%d?)%.(%d%d?%d?)%.(%d%d?%d?)%.(%d%d?%d?)$"
local interface_pattern = "^[a-zA-Z]+-[0-9]+/[0-9]+/[0-9]+$"

-- Utility functions
local function validate_ip(ip)
    if not ip then return false end
    local chunks = {ip:match(ipv4_pattern)}
    if #chunks ~= 4 then return false end
    for _, v in ipairs(chunks) do
        if tonumber(v) > 255 then return false end
    end
    return true
end

local function parse_timestamp(ts)
    -- Add sophisticated timestamp parsing logic here
    -- Returns unix timestamp in milliseconds
    return os.time() * 1000 -- Placeholder
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure with required fields
    local output = {
        class_uid = 4002,
        class_name = "Network Activity",
        category_uid = 4,
        category_name = "Network Activity",
        metadata = {
            product = {
                name = "Juniper Networks Equipment",
                vendor_name = "Juniper Networks"
            },
            version = "1.0.0"
        },
        time = parse_timestamp(record.timestamp),
        severity_id = record.severity_id or 2
    }

    -- Network interface handling
    if record.interface then
        if record.interface:match(interface_pattern) then
            output.network = {
                interface = {
                    name = record.interface
                }
            }
        end
    end

    -- Source/Destination IP handling
    if record.src_ip then
        if validate_ip(record.src_ip) then
            output.src_endpoint = {
                ip = record.src_ip,
                port = tonumber(record.src_port)
            }
        end
    end

    if record.dst_ip then
        if validate_ip(record.dst_ip) then
            output.dst_endpoint = {
                ip = record.dst_ip,
                port = tonumber(record.dst_port)
            }
        end
    end

    -- Additional fields based on message type
    if record.process and record.pid then
        output.process = {
            name = record.process,
            pid = tonumber(record.pid)
        }
    end

    -- Protocol and service info
    if record.protocol then
        output.network = output.network or {}
        output.network.protocol = string.upper(record.protocol)
    end

    -- Validation and cleanup
    if not output.time then
        output.time = os.time() * 1000
    end

    return output
end