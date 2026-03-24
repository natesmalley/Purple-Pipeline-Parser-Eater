-- SentinelOne Parser: f5_networks_logs-latest 
-- OCSF Class: Network Traffic (5002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:59:06.265951

-- Pre-compile patterns for performance
local ipv4_pattern = "^(%d%d?%d?)%.(%d%d?%d?)%.(%d%d?%d?)%.(%d%d?%d?)$"
local timestamp_pattern = "^(%d%d%d%d)/(%d%d)/(%d%d)%s+(%d%d):(%d%d):(%d%d)$"

-- Cached functions for performance
local tonumber = tonumber
local type = type
local os_time = os.time
local string_match = string.match
local string_format = string.format

-- IP address validation helper
local function validate_ip(ip)
    if not ip then return false end
    local p1,p2,p3,p4 = string_match(ip, ipv4_pattern)
    if not p1 then return false end
    p1,p2,p3,p4 = tonumber(p1),tonumber(p2),tonumber(p3),tonumber(p4)
    return p1 and p1 <= 255 and p2 and p2 <= 255 and 
           p3 and p3 <= 255 and p4 and p4 <= 255
end

-- Timestamp parser helper
local function parse_timestamp(ts)
    if not ts then return nil end
    local y,m,d,h,min,s = string_match(ts, timestamp_pattern)
    if not y then return nil end
    return string_format("%s-%s-%sT%s:%s:%sZ",y,m,d,h,min,s)
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with required fields
    local output = {
        class_uid = 5002,
        class_name = "F5 Web Traffic",
        category_uid = 4, 
        category_name = "F5 HTTP Access Logs",
        metadata = {
            product = {
                name = "F5 BIG-IP",
                vendor_name = "F5 Networks"
            }
        },
        dataSource = {
            category = "network",
            name = "F5 BIG-IP",
            vendor = "F5"
        }
    }

    -- Process timestamp
    local timestamp = record.timestamp
    if timestamp then
        local parsed_time = parse_timestamp(timestamp)
        if parsed_time then
            output.time = parsed_time
        else
            output.time = os_time() * 1000 -- Fallback to current time
        end
    end

    -- Process source IP
    local src_ip = record.ipv4
    if src_ip and validate_ip(src_ip) then
        output.src_endpoint = {
            ip = src_ip,
            type = "ipv4"
        }
    end

    -- Validation and cleanup
    if not output.time then
        output.time = os_time() * 1000
    end

    -- Add observability metadata
    output._observo = {
        parser_version = "latest",
        processing_time = os_time(),
        source_format = "f5_networks_logs"
    }

    return output
end

-- Error handler wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end