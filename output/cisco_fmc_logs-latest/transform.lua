-- SentinelOne Parser: cisco_fmc_logs-latest 
-- OCSF Class: Network Activity (4001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:53:24.136271

-- Pre-declare locals for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_format = string.format
local ipairs = ipairs

-- Validation helper functions
local function validate_ip(ip)
    if not ip then return false end
    local parts = {ip:match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")}
    if #parts ~= 4 then return false end
    for _, part in ipairs(parts) do
        local n = tonumber(part)
        if not n or n < 0 or n > 255 then return false end
    end
    return true
end

local function validate_port(port)
    local n = tonumber(port)
    return n and n >= 0 and n <= 65535
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with constants
    local output = {
        class_uid = 4001,
        class_name = "Network Activity",
        category_uid = 4, 
        category_name = "Network Activity",
        metadata = {
            product = {
                name = "Cisco FMC",
                vendor_name = "Cisco"
            },
            version = "1.0.0"
        }
    }

    -- Timestamp handling with validation
    local timestamp = record.unmapped and record.unmapped.timestamp
    if timestamp then
        local ts = tonumber(timestamp)
        if ts then
            output.time = ts
        end
    end
    
    -- Network endpoint processing
    if record.unmapped then
        local unmapped = record.unmapped
        
        -- Source endpoint
        if validate_ip(unmapped.source_ip) then
            output.src_endpoint = output.src_endpoint or {}
            output.src_endpoint.ip = unmapped.source_ip
            if validate_port(unmapped.source_port) then
                output.src_endpoint.port = tonumber(unmapped.source_port)
            end
        end

        -- Destination endpoint
        if validate_ip(unmapped.destination_ip) then
            output.dst_endpoint = output.dst_endpoint or {}
            output.dst_endpoint.ip = unmapped.destination_ip
            if validate_port(unmapped.destination_port) then
                output.dst_endpoint.port = tonumber(unmapped.destination_port)
            end
        end

        -- Traffic metrics with type validation
        local traffic = {}
        local has_traffic = false
        
        if tonumber(unmapped.bytes_sent) then
            traffic.bytes_out = tonumber(unmapped.bytes_sent)
            has_traffic = true
        end
        if tonumber(unmapped.bytes_received) then
            traffic.bytes_in = tonumber(unmapped.bytes_received)
            has_traffic = true
        end
        if tonumber(unmapped.packets_sent) then
            traffic.packets_out = tonumber(unmapped.packets_sent)
            has_traffic = true
        end
        if tonumber(unmapped.packets_received) then
            traffic.packets_in = tonumber(unmapped.packets_received)
            has_traffic = true
        end
        
        if has_traffic then
            output.traffic = traffic
        end

        -- Device info
        if unmapped.device_name or unmapped.device_ip then
            output.device = {
                name = unmapped.device_name,
                ip = unmapped.device_ip
            }
        end

        -- Policy and rule info
        if unmapped.policy_name then
            output.policy = {
                name = unmapped.policy_name
            }
        end
        if unmapped.rule_name then
            output.rule = {
                name = unmapped.rule_name
            }
        end

        -- Direct field mappings
        output.uid = unmapped.event_id
        output.type_name = unmapped.event_type
        output.severity = tonumber(unmapped.severity)
        output.action = unmapped.action
        output.duration = tonumber(unmapped.duration)
        
        if unmapped.protocol then
            output.connection_info = {
                protocol_name = unmapped.protocol
            }
        end
    end

    -- Validation of required fields
    if not output.time then
        output.time = os_time() * 1000
    end

    if not output.uid then
        output.uid = string_format("fmc_%d", output.time)
    end

    return output
end

-- Error handling wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end