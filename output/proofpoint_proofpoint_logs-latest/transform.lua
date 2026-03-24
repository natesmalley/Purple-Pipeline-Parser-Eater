--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: proofpoint_proofpoint_logs-latest
  Generated: 2025-10-13T11:48:39.981966
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: proofpoint_proofpoint_logs-latest 
-- OCSF Class: Email Activity (6001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T11:12:03.674622

-- Pre-compile patterns for performance
local PATTERNS = {
    ip = "^%d+%.%d+%.%d+%.%d+$",
    email = "^[%w%.%-]+@[%w%.%-]+%.%w+$"
}

-- Local helper functions for performance
local function validate_email(str)
    return str and string.match(str, PATTERNS.email)
end

local function validate_ip(str) 
    return str and string.match(str, PATTERNS.ip)
end

local function safe_copy(src, dest, field_map)
    for src_field, dest_field in pairs(field_map) do
        if src[src_field] then
            dest[dest_field] = src[src_field]
        end
    end
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local references
    local output = {
        class_uid = 6001,
        class_name = "Email Activity", 
        category_uid = 6,
        category_name = "Communications Security",
        activity_id = 1,
        type_uid = 600101,
        metadata = {
            version = "1.0.0",
            product = {
                name = "Proofpoint Email Security",
                vendor = "Proofpoint"
            }
        },
        email_activity = {},
        email = {},
        threat = {},
        message = {},
        device = {}
    }

    -- Efficient field mapping using local tables
    local email_fields = {
        fromAddress = "from_address",
        headerFrom = "from",
        headerReplyTo = "reply_to",
        toAddresses = "delivered_to",
        ccAddresses = "cc",
        subject = "subject"
    }
    
    local threat_fields = {
        threatID = "id",
        threatStatus = "status",
        threatType = "type",
        threatUrl = "url"
    }

    -- Optimized batch field copying
    safe_copy(record, output.email, email_fields)
    safe_copy(record, output.threat, threat_fields)

    -- Handle critical fields with validation
    if record.messageTime then
        output.email_activity.time_dt = record.messageTime
        output.time = record.messageTime -- OCSF required field
    else
        output.time = os.time() * 1000
    end

    -- Validate and transform email addresses
    if record.sender and validate_email(record.sender) then
        output.email.sender_email = record.sender
    end

    -- Handle IP addresses with validation
    if record.senderIP and validate_ip(record.senderIP) then
        output.email.sender_ip = record.senderIP
    end

    -- Transform scores with type checking
    if record.phishScore and type(record.phishScore) == "number" then
        output.email_activity.severity = record.phishScore
    end

    if record.spamScore and type(record.spamScore) == "number" then
        output.device.risk_score = record.spamScore
    end

    -- Process threatsInfoMap if present
    if record.threatsInfoMap and type(record.threatsInfoMap) == "table" then
        local threat_info = record.threatsInfoMap[1] -- Take first threat
        if threat_info then
            output.threat.classification = threat_info.classification
            output.threat.name = threat_info.threat
            output.threat.time = threat_info.threatTime
        end
    end

    -- Final validation of required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    return output
end