--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: zscaler_dns_firewall-latest
  Generated: 2025-10-13T12:41:10.865101
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: zscaler_dns_firewall-latest 
-- OCSF Class: DNS Activity (4003)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:05:28.957657

-- Pre-declare locals for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_match = string.match
local ipv4_pattern = "^%d+%.%d+%.%d+%.%d+$"

-- Validation helper functions
local function validate_ip(ip)
    if not ip then return false end
    return string_match(ip, ipv4_pattern) ~= nil
end

local function validate_email(email)
    if not email then return false end
    return string_match(email, "^[%w%.%-]+@[%w%.%-]+%.%w+$") ~= nil
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with constant fields
    local output = {
        -- Classification constants
        activity_id = 6,
        activity_name = "Traffic",
        category_uid = 4,
        category_name = "Network Activity", 
        class_uid = 4003,
        class_name = "DNS Activity",
        type_uid = 400306,
        type_name = "DNS Activity: Traffic",
        cloud = {
            provider = "Zscaler"
        }
    }

    -- Timestamp handling with validation
    if record.timestamp then
        local ts = tonumber(record.timestamp)
        if ts then
            output.time = ts
        else
            -- Try parsing ISO8601
            local year, month, day, hour, min, sec = string_match(record.timestamp,
                "(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)")
            if year then
                output.time = os_time({
                    year = tonumber(year),
                    month = tonumber(month),
                    day = tonumber(day),
                    hour = tonumber(hour),
                    min = tonumber(min),
                    sec = tonumber(sec)
                })
            end
        end
    end

    -- Actor information
    if record.userName and validate_email(record.userName) then
        output.actor = {
            user = {
                email_addr = record.userName
            }
        }
    end

    -- Source endpoint
    if record.sourceIp and validate_ip(record.sourceIp) then
        output.src_endpoint = {
            ip = record.sourceIp
        }
    end

    -- Device information
    if record.deviceId then
        output.device = {
            uid = record.deviceId
        }
    end

    -- DNS Query details
    if record.query then
        output.query = {
            hostname = record.query,
            type = record.queryType
        }
    end

    -- Response details
    if record.responseCode then
        output.rcode = tonumber(record.responseCode) or record.responseCode
    end
    
    if record.answer then
        output.answers = record.answer
    end

    -- Policy and disposition
    if record.action then
        output.disposition = record.action
    end
    
    if record.policyId then
        output.policy = {
            uid = record.policyId
        }
    end

    -- Threat categorization
    if record.threatCategory then
        output.malware = {
            classification_ids = record.threatCategory
        }
    end

    -- Final validation
    if not output.time then
        output.time = os_time() * 1000
    end

    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    return output
end