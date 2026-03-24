-- SentinelOne Parser: armis_armis_logs-latest 
-- OCSF Class: Security Finding (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-16T14:57:56.601925

-- Pre-declare locals for performance
local type = type
local pairs = pairs
local os_time = os.time
local string_format = string.format
local table_insert = table.insert

-- Validation helper functions
local function validate_string(val)
    return type(val) == "string" and val ~= ""
end

local function validate_number(val) 
    return type(val) == "number"
end

-- Main transform function
function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize output with required OCSF fields
    local output = {
        metadata = {
            version = "1.0.0",
            class_uid = 1001,
            class_name = "Security Finding",
            category_uid = 1, 
            category_name = "Security Events"
        },
        security_finding = {},
        event = {},
        policy = {}
    }

    -- Optimized field mapping with validation
    local security_finding = output.security_finding
    local event = output.event
    local policy = output.policy

    -- Map security finding fields
    if validate_string(record.id) then
        security_finding.activity_id = record.id
    end

    if validate_string(record.content) then
        security_finding.data = record.content
    end

    if validate_string(record.description) then
        security_finding.message = record.description
    end

    -- Map time with validation
    if record._time then
        local time_val = tonumber(record._time)
        if time_val then
            security_finding.time = time_val
        end
    end

    -- Map event type
    if validate_string(record.type) then
        event.type = record.type
    end

    -- Map policy fields efficiently
    if record.policy then
        local src_policy = record.policy
        
        if validate_string(src_policy.actionType) then
            policy.action_id = src_policy.actionType
        end

        if validate_string(src_policy.actionTypeDisplay) then
            policy.action_name = src_policy.actionTypeDisplay
        end

        if validate_string(src_policy.alertClassificationId) then
            policy.uid = src_policy.alertClassificationId
        end

        -- Handle nested policy.actionParams
        if src_policy.actionParams then
            local action_params = src_policy.actionParams
            
            if validate_string(action_params.alertClassificationId) then
                policy.type_id = action_params.alertClassificationId
            end

            if validate_string(action_params.alertDescription) then
                policy.type = action_params.alertDescription
            end

            if action_params.emailRecipients then
                policy.delivered_to = action_params.emailRecipients
            end
        end

        -- Map boolean fields
        policy.is_active = src_policy.isActive == true
        policy.is_boundary = src_policy.isBoundary == true
        policy.is_editable = src_policy.isEditable == true
    end

    -- Add default timestamp if missing
    if not security_finding.time then
        security_finding.time = os_time() * 1000
    end

    -- Validate required fields
    if not security_finding.activity_id then
        return nil, "Missing required field: security_finding.activity_id"
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