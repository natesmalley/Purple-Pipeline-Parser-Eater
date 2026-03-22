-- SentinelOne Parser: cisco_asa_logs-latest 
-- OCSF Class: Network Activity (4001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:53:03.706007

-- Pre-compile patterns for performance
local TIMESTAMP_PATTERN = "^(%w+%s+%d+%s+%d+%s+%d+:%d+:%d+)"
local IP_PATTERN = "^%d+%.%d+%.%d+%.%d+$"

-- Cache frequently used functions
local type = type
local tonumber = tonumber
local os_time = os.time
local string_match = string.match
local string_format = string.format

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local table
    local output = {
        -- Mandatory OCSF fields
        class_uid = 4001,
        class_name = "Network Activity", 
        category_uid = 4,
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = 400101,
        
        -- Initialize nested tables
        src_endpoint = {},
        dst_endpoint = {},
        metadata = {
            product = {
                name = "Cisco ASA",
                vendor_name = "Cisco"
            }
        },
        dataSource = {
            category = "security",
            name = "Cisco ASA", 
            vendor = "Cisco"
        }
    }

    -- Local variables for repeated access
    local src = record.src or {}
    local dst = record.dst or {}
    
    -- Optimized field transformations
    -- Source IP handling
    if src.ip and src.ip.address and string_match(src.ip.address, IP_PATTERN) then
        output.src_endpoint.ip = src.ip.address
    end

    -- Destination IP handling  
    if dst.ip and dst.ip.address and string_match(dst.ip.address, IP_PATTERN) then
        output.dst_endpoint.ip = dst.ip.address
    end

    -- Alert code handling with validation
    if record["Alert-Code"] then
        local alert_code = tonumber(record["Alert-Code"])
        if alert_code then
            output.alert_code = alert_code
        end
    end

    -- Timestamp handling
    if record.timestamp then
        local ts = string_match(record.timestamp, TIMESTAMP_PATTERN)
        if ts then
            -- Convert timestamp to UNIX milliseconds
            -- Using placeholder conversion - implement actual conversion logic
            output.time = os_time() * 1000
        end
    else
        output.time = os_time() * 1000
    end

    -- Severity mapping
    if record.severity then
        local severity = tonumber(record.severity)
        if severity then
            output.severity = severity
        end
    end

    -- Protocol handling
    if record.protocol then
        output.network = output.network or {}
        output.network.protocol = string.upper(record.protocol)
    end

    -- Connection details
    if record.connection and record.connection.id then
        output.connection_info = output.connection_info or {}
        output.connection_info.id = record.connection.id
    end

    -- Validation and cleanup
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    -- Remove empty tables
    for k, v in pairs(output) do
        if type(v) == "table" and next(v) == nil then
            output[k] = nil
        end
    end

    return output
end

-- Error handler wrapper
function safe_transform(record)
    local status, result = pcall(transform, record)
    if status then
        return result
    else
        return nil, string_format("Transform error: %s", result)
    end
end