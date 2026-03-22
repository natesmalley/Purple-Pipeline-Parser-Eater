-- SentinelOne Parser: manch_siem_logs-latest 
-- OCSF Class: Detection Finding (2001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:05:09.743124

-- Pre-compile regex patterns for performance
local timestamp_pattern = "^%d%d%d%d%-%d%d%-%d%dT%d%d:%d%d:%d%d"
local ipv4_pattern = "^%d+%.%d+%.%d+%.%d+$"

-- Cached string formats for performance
local ip_format = "%d.%d.%d.%d"
local time_format = "%Y-%m-%dT%H:%M:%S"

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local table
    local output = {
        -- Required OCSF fields
        class_uid = 2001,
        class_name = "Detection Finding",
        category_uid = 2,
        category_name = "Findings",
        activity_id = 1,
        type_uid = 200101,
        
        -- Initialize nested structures
        metadata = {
            product = {
                name = "Manch SIEM",
                vendor_name = "Manch"
            },
            version = "1.0.0"
        },
        
        -- Initialize endpoints
        src_endpoint = {},
        dst_endpoint = {},
        
        -- Initialize user context
        user = {}
    }

    -- Timestamp transformation with validation
    if record.timestamp then
        local success, timestamp = pcall(function()
            return os.time({
                year = string.sub(record.timestamp, 1, 4),
                month = string.sub(record.timestamp, 6, 7),
                day = string.sub(record.timestamp, 9, 10),
                hour = string.sub(record.timestamp, 12, 13),
                min = string.sub(record.timestamp, 15, 16),
                sec = string.sub(record.timestamp, 18, 19)
            }) * 1000
        end)
        
        if success then
            output.time = timestamp
        else
            output.time = os.time() * 1000 -- Fallback to current time
        end
    end

    -- IP address transformations with validation
    if record.src_ip and string.match(record.src_ip, ipv4_pattern) then
        output.src_endpoint.ip = record.src_ip
    end
    
    if record.dst_ip and string.match(record.dst_ip, ipv4_pattern) then
        output.dst_endpoint.ip = record.dst_ip
    end

    -- User transformation with sanitization
    if record.user then
        output.user.name = string.gsub(record.user, "[^%w%s%-_@%.]", "") -- Sanitize username
    end

    -- Additional field mappings based on event type
    if record.alert_name then
        output.finding = {
            title = record.alert_name,
            description = record.description or "No description provided"
        }
        output.severity_id = tonumber(record.severity) or 3
    end

    -- Validation of required OCSF fields
    if not output.time then
        output.time = os.time() * 1000
    end

    if not output.severity_id then
        output.severity_id = 3 -- Default severity
    end

    -- Clean empty tables for efficiency
    if next(output.src_endpoint) == nil then output.src_endpoint = nil end
    if next(output.dst_endpoint) == nil then output.dst_endpoint = nil end
    if next(output.user) == nil then output.user = nil end

    return output
end

-- Error handler wrapper for production use
function safe_transform(record)
    local success, result, error = pcall(transform, record)
    if success then
        return result, error
    else
        return nil, "Transform error: " .. tostring(result)
    end
end