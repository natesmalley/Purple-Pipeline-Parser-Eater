-- SentinelOne Parser: cyberark_pas_logs-latest 
-- OCSF Class: Policy Activity (6001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:58:10.669493

-- Pre-declare locals for performance
local type = type
local pairs = pairs
local os_time = os.time
local string_format = string.format

-- Validation helper functions
local function validate_string(value)
    return type(value) == "string" and #value > 0
end

local function validate_number(value) 
    return type(value) == "number"
end

-- Main transform function
function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize output structure with required OCSF fields
    local output = {
        metadata = {
            version = "1.0.0",
            class_uid = 6001,
            class_name = "Policy Activity", 
            category_uid = 6,
            category_name = "Security Management"
        },
        policy = {},
        fingerprint = {},
        event = {},
        digital_signature = {},
        resource = {},
        policy_audit = {},
        user = {},
        file = {},
        threat_protection = {}
    }

    -- Optimized field mapping with validation
    local field_mappings = {
        -- Direct mappings
        {src = "policyName", dest = "policy.name", validate = validate_string},
        {src = "hash", dest = "fingerprint.value", validate = validate_string},
        {src = "publisher", dest = "digital_signature.company_name", validate = validate_string},
        {src = "eventType", dest = "event.type", validate = validate_string},
        {src = "sourceType", dest = "resource.type", validate = validate_string},
        {src = "sourceName", dest = "resource.name", validate = validate_string},
        {src = "userName", dest = "user.name", validate = validate_string},
        {src = "justificationEmail", dest = "user.email_addr", validate = validate_string},
        {src = "justification", dest = "policy_audit.justification", validate = validate_string},
        {src = "fileName", dest = "policy_audit.file", validate = validate_string},
        {src = "originalFileName", dest = "file.name", validate = validate_string},
        {src = "fileSize", dest = "file.size", validate = validate_number},
        {src = "threatProtectionAction", dest = "threat_protection.action", validate = validate_string},
        {src = "threatProtectionActionId", dest = "threat_protection.action_id", validate = validate_string}
    }

    -- Process field mappings efficiently
    for _, mapping in pairs(field_mappings) do
        local value = record[mapping.src]
        if value and mapping.validate(value) then
            -- Split the destination path and create nested tables as needed
            local dest_parts = {}
            for part in mapping.dest:gmatch("[^%.]+") do
                dest_parts[#dest_parts + 1] = part
            end
            
            local current = output
            for i = 1, #dest_parts - 1 do
                if not current[dest_parts[i]] then
                    current[dest_parts[i]] = {}
                end
                current = current[dest_parts[i]]
            end
            current[dest_parts[#dest_parts]] = value
        end
    end

    -- Handle timestamps
    if record.lastEventDate then
        output.policy_audit.end_time = record.lastEventDate
    end
    if record.firstEventDate then
        output.policy_audit.start_time = record.firstEventDate
    end

    -- Add default timestamp if none exists
    if not output.time then
        output.time = os_time() * 1000
    end

    -- Validate required OCSF fields
    if not output.metadata.class_uid then
        return nil, "Missing required OCSF class_uid"
    end

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