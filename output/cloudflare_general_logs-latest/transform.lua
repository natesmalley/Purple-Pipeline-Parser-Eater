-- SentinelOne Parser: cloudflare_general_logs-latest 
-- OCSF Class: Network Activity (4001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:56:49.471695

-- Pre-compile patterns for performance
local EMAIL_PATTERN = "^[%w%.%-]+@[%w%.%-]+%.%w+$"
local IP_PATTERN = "^%d+%.%d+%.%d+%.%d+$"
local TIMESTAMP_PATTERN = "^%d+%.?%d*$"

-- Cached string functions for performance
local format = string.format
local match = string.match
local type = type
local tonumber = tonumber

-- Helper functions
local function validate_email(email)
    return type(email) == "string" and match(email, EMAIL_PATTERN) ~= nil
end

local function validate_ip(ip)
    return type(ip) == "string" and match(ip, IP_PATTERN) ~= nil
end

local function parse_timestamp(ts)
    if type(ts) == "number" then return ts end
    if type(ts) == "string" and match(ts, TIMESTAMP_PATTERN) then
        return tonumber(ts)
    end
    return nil
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize output structure with required OCSF fields
    local output = {
        metadata = {
            version = "1.0.0",
            product = {
                vendor_name = "Cloudflare",
                name = "Enterprise Logs"
            }
        },
        class_uid = 4001,
        class_name = "Network Activity", 
        category_uid = 4,
        category_name = "Network Activity",
        activity_id = 99, -- Default activity
        severity_id = 99, -- Default severity
        time = os.time() -- Default timestamp
    }

    -- Actor information handling
    if record.Email then
        if not validate_email(record.Email) then
            return nil, format("Invalid email format: %s", record.Email)
        end
        
        -- Initialize actor structure
        output.actor = {
            user = {
                email_addr = record.Email,
                -- Extract username from email
                name = match(record.Email, "([^@]+)@"),
                -- Extract domain from email  
                domain = match(record.Email, "@(.+)")
            }
        }
    end

    -- Source endpoint handling
    if record.IPAddress then
        if not validate_ip(record.IPAddress) then
            return nil, format("Invalid IP format: %s", record.IPAddress)
        end
        
        output.src_endpoint = {
            ip = record.IPAddress,
            category = "ipv4-addr"
        }
    end

    -- Timestamp handling with validation
    if record.CreatedAt then
        local ts = parse_timestamp(record.CreatedAt)
        if not ts then
            return nil, format("Invalid timestamp format: %s", record.CreatedAt)
        end
        output.time = ts
    end

    -- HTTP request handling if present
    if record.HTTPMethod or record.URL then
        output.http_request = {
            http_method = record.HTTPMethod,
            url = {
                url_string = record.URL
            }
        }
    end

    -- Status handling
    if record.Allowed ~= nil then
        output.status_id = record.Allowed and 1 or 2
    end

    -- Validation of required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Missing required class_uid"
    end

    -- Add processing metadata
    output.metadata.processed_at = os.time()
    
    return output
end

-- Error handler wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, format("Transform error: %s", result)
    end
    return result
end