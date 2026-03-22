--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: marketplace-zscalerprivateaccessjson-latest
  Generated: 2025-10-13T12:46:33.480234
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: marketplace-zscalerprivateaccessjson-latest 
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:06:01.288433

-- Pre-compile patterns for performance
local PATTERNS = {
    connector_status = "^Connector Status zpa%-lss$",
    user_activity = "^User Activity zpa%-lss$", 
    user_status = "^User Status zpa%-lss$",
    audit = "^Audit zpa%-lss$"
}

-- Cached constants for memory efficiency
local CONSTANTS = {
    product = {
        name = "Zscaler Private Access",
        vendor = "Zscaler",
        version = "1.0.0-rc.3"
    },
    datasource = {
        category = "security",
        name = "Zscaler Private Access",
        vendor = "Zscaler"
    }
}

-- Main transform function
function transform(record)
    -- Input validation
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize output with common fields
    local output = {
        metadata = {
            product = {
                name = CONSTANTS.product.name,
                vendor_name = CONSTANTS.product.vendor,
                version = CONSTANTS.product.version
            },
            version = "1.0.0-rc.3"
        },
        dataSource = {
            category = CONSTANTS.datasource.category,
            name = CONSTANTS.datasource.name,
            vendor = CONSTANTS.datasource.vendor
        },
        severity_id = 0
    }

    -- Extract event type
    local event_type = record.EventType
    if not event_type then
        return nil, "Missing EventType field"
    end

    -- Process based on event type
    if string.match(event_type, PATTERNS.connector_status) then
        process_connector_status(record, output)
    elseif string.match(event_type, PATTERNS.user_activity) then
        process_user_activity(record, output)
    elseif string.match(event_type, PATTERNS.user_status) then
        process_user_status(record, output)
    elseif string.match(event_type, PATTERNS.audit) then
        process_audit(record, output)
    else
        return nil, string.format("Unsupported EventType: %s", event_type)
    end

    -- Map common fields
    if record.LogTimestamp then
        output.metadata.original_time = record.LogTimestamp
    end
    if record.SessionID then
        output.actor = output.actor or {}
        output.actor.session = output.actor.session or {}
        output.actor.session.uid = record.SessionID
    end
    if record.Username then
        output.actor = output.actor or {}
        output.actor.user = output.actor.user or {}
        output.actor.user.name = record.Username
    end

    -- Validation
    if not validate_output(output) then
        return nil, "Output validation failed"
    end

    return output
end

-- Process Connector Status events
function process_connector_status(record, output)
    output.class_uid = 6001
    output.class_name = "Web Resources Activity"
    output.category_uid = 6
    output.category_name = "Application Activity"
    output.activity_id = 99
    output.type_uid = 600199
    
    -- Map specific fields
    if record.Platform then
        output.device = output.device or {}
        output.device.os = output.device.os or {}
        output.device.os.name = record.Platform
    end
end

-- Process User Activity events  
function process_user_activity(record, output)
    output.class_uid = 6001
    output.class_name = "Web Resources Activity"
    output.category_uid = 6
    output.category_name = "Application Activity"
    output.activity_id = 99
    output.type_uid = 600199

    -- Map connection info
    if record.IPProtocol then
        output.connection_info = output.connection_info or {}
        output.connection_info.protocol_num = record.IPProtocol
    end
end

-- Process User Status events
function process_user_status(record, output) 
    output.class_uid = 6001
    output.class_name = "Web Resources Activity"
    output.category_uid = 6
    output.category_name = "Application Activity"
    output.activity_id = 99
    output.type_uid = 600199

    -- Map session times
    if record.TimestampAuthentication then
        output.actor = output.actor or {}
        output.actor.session = output.actor.session or {}
        output.actor.session.created_time = record.TimestampAuthentication
    end
end

-- Process Audit events
function process_audit(record, output)
    output.class_uid = 3004
    output.class_name = "Entity Management"
    output.category_uid = 3
    output.category_name = "Identity & Access Management"
    
    -- Map audit specific fields
    if record.AuditOperationType then
        local op_type = record.AuditOperationType
        if op_type == "Create" then
            output.activity_id = 3
            output.type_uid = 300401
        elseif op_type == "Update" then
            output.activity_id = 1
            output.type_uid = 300403
        elseif op_type == "Delete" then
            output.activity_id = 4
            output.type_uid = 300404
        else
            output.activity_id = 99
            output.type_uid = 300499
        end
    end
end

-- Validate output structure
function validate_output(output)
    return output.class_uid and 
           output.class_name and
           output.category_uid and
           output.category_name and
           output.activity_id and
           output.type_uid
end

return transform