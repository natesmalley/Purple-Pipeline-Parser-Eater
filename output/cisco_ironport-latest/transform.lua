-- SentinelOne Parser: cisco_ironport-latest 
-- OCSF Class: Email Activity (4009)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:54:09.148599

-- Pre-declare locals for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_match = string.match
local string_format = string.format

-- Email validation pattern
local EMAIL_PATTERN = "^[%w%.%-]+@[%w%.%-]+%.%w+$"

-- Validation helper functions
local function validate_email(email)
    if not email then return false end
    return string_match(email, EMAIL_PATTERN) ~= nil
end

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

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure with constants
    local output = {
        activity_id = 1,
        activity_name = "Send",
        category_uid = 4,
        category_name = "Network Activity", 
        class_uid = 4009,
        class_name = "Email Activity",
        type_uid = 400901,
        type_name = "Email Activity: Send"
    }

    -- Timestamp handling with validation
    local timestamp = record.unmapped and record.unmapped.timestamp
    if timestamp then
        local ts = tonumber(timestamp)
        if ts then
            output.time = ts
        end
    end
    
    -- Email field mappings with validation
    if record.unmapped then
        local unmapped = record.unmapped
        
        -- Email metadata
        if unmapped.message_id then
            output.email = output.email or {}
            output.email.uid = unmapped.message_id
        end

        -- Validate and map email addresses
        if unmapped.from_address and validate_email(unmapped.from_address) then
            output.email = output.email or {}
            output.email.from = unmapped.from_address
        end

        if unmapped.to_address and validate_email(unmapped.to_address) then
            output.email = output.email or {}
            output.email.to = unmapped.to_address
        end

        -- Subject with sanitization
        if unmapped.subject then
            output.email = output.email or {}
            output.email.subject = string_format("%s", unmapped.subject:gsub("[^%w%s%-_%.@]", ""))
        end

        -- Endpoint information with IP validation
        if unmapped.src_ip and validate_ip(unmapped.src_ip) then
            output.src_endpoint = output.src_endpoint or {}
            output.src_endpoint.ip = unmapped.src_ip
        end

        if unmapped.dst_ip and validate_ip(unmapped.dst_ip) then
            output.dst_endpoint = output.dst_endpoint or {}
            output.dst_endpoint.ip = unmapped.dst_ip
        end

        -- Hostname sanitization
        if unmapped.hostname then
            output.src_endpoint = output.src_endpoint or {}
            output.src_endpoint.hostname = string_format("%s", unmapped.hostname:gsub("[^%w%-_%.:]", ""))
        end

        -- Verdict and classification fields
        if unmapped.verdict then
            output.disposition = unmapped.verdict
        end

        if unmapped.antispam_verdict then
            output.email = output.email or {}
            output.email.smtp_hello = unmapped.antispam_verdict
        end

        if unmapped.antivirus_verdict then
            output.malware = output.malware or {}
            output.malware.name = unmapped.antivirus_verdict
        end
    end

    -- Final validation
    if not output.time then
        output.time = os_time() * 1000
    end

    if not output.email then
        return nil, "Missing required email fields"
    end

    return output
end

-- Error handling wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end