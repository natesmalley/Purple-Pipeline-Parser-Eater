-- SentinelOne Parser: microsoft_eventhub_azure_signin_logs-latest 
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:06:29.043637

-- Local cache for improved performance
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

    -- Initialize OCSF-compliant output with required fields
    local output = {
        class_uid = 3002,
        class_name = "Authentication",
        category_uid = 3, 
        category_name = "Identity & Access Management",
        activity_id = 1,
        type_uid = 300201,
        metadata = {
            version = "1.0.0",
            product = {
                name = "Azure Event Hub",
                vendor_name = "Microsoft"
            }
        }
    }

    -- Optimized field transformations
    local signin_event = record.signin_event
    if validate_string(signin_event) then
        output.activity_name = signin_event
    end

    -- Extract timestamp with fallback
    local event_time = record.time or record.timestamp or record.eventTime
    if validate_number(event_time) then
        output.time = event_time
    else
        output.time = os_time() * 1000 -- Convert to milliseconds
    end

    -- Extract authentication details if available
    if record.user then
        output.actor = {
            user = {
                name = record.user.name,
                uid = record.user.id,
                type = "User"
            }
        }
    end

    -- Add status information
    if record.status then
        output.status = record.status
        output.status_detail = record.status_detail or record.statusDetail
    end

    -- Validation of required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    if not output.activity_name then
        output.activity_name = "Unknown Authentication Event"
    end

    -- Add correlation data if available
    if record.correlation_id then
        output.correlation_uid = record.correlation_id
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