-- SentinelOne Parser: abnormal_security_logs-latest 
-- OCSF Class: Email Activity (2001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-16T14:56:12.133329

-- Pre-compile regex patterns for performance
local email_pattern = "^[%w%.%%%+%-]+@[%w%.%-]+%.%w+$"
local timestamp_pattern = "^%d%d%d%d%-%d%d%-%d%dT%d%d:%d%d:%d%d"

-- Cached reference to frequently used functions
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

    -- Initialize OCSF-compliant output with local references
    local output = {
        -- Required OCSF fields
        class_uid = 2001,
        class_name = "Email Activity", 
        category_uid = 2,
        category_name = "Findings",
        activity_id = 1,
        type_uid = 200101,
        metadata = {
            product = {
                name = "Abnormal Security",
                vendor_name = "Abnormal"
            },
            version = "1.0.0"
        },
        time = nil,
        finding = {},
        email = {},
        user = {}
    }

    -- Timestamp processing with validation
    if record.timestamp then
        local ts = string_match(record.timestamp, timestamp_pattern)
        if ts then
            output.time = ts
        end
    end
    
    -- Default timestamp if not set
    if not output.time then
        output.time = os_time() * 1000
    end

    -- Email sender validation and transformation
    if record.sender_email then
        if string_match(record.sender_email, email_pattern) then
            output.email.sender = record.sender_email
        end
    end

    -- User email validation and transformation 
    if record.user_email then
        if string_match(record.user_email, email_pattern) then
            output.user.email = record.user_email
        end
    end

    -- Threat type mapping
    if record.threat_type then
        output.finding.type = record.threat_type
        -- Set severity based on threat type
        output.severity_id = record.threat_type:match("critical") and 4 or 2
    end

    -- Additional email metadata
    if record.subject then
        output.email.subject = record.subject
    end

    -- IP address handling
    if record.src_ip then
        output.src_endpoint = {ip = record.src_ip}
    end

    -- Validation of required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    -- Clean empty tables for efficiency
    if next(output.finding) == nil then output.finding = nil end
    if next(output.email) == nil then output.email = nil end
    if next(output.user) == nil then output.user = nil end

    return output
end

-- Error wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end