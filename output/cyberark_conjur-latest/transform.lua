-- SentinelOne Parser: cyberark_conjur-latest 
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:58:09.665248

-- Pre-declare locals for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_format = string.format

-- Constant OCSF field values
local OCSF_CONSTANTS = {
    class_uid = 3002,
    class_name = "Authentication",
    category_uid = 3, 
    category_name = "Identity & Access Management",
    activity_id = 1,
    type_uid = 300201,
    type_name = "Authentication: Logon"
}

-- Validate timestamp format and convert to epoch
local function parse_timestamp(ts)
    if not ts then return nil end
    local epoch = tonumber(ts)
    if epoch then return epoch end
    -- Add ISO8601 parsing if needed
    return os_time() * 1000
end

-- Normalize status values
local function normalize_status(status)
    if not status then return "unknown" end
    status = string.lower(status)
    if status == "success" or status == "succeeded" then
        return "success"
    elseif status == "fail" or status == "failed" then
        return "failure"  
    end
    return "unknown"
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Access unmapped table safely
    local unmapped = record.unmapped
    if not unmapped then
        return nil, "Missing unmapped data"
    end

    -- Initialize OCSF-compliant output structure
    local output = {
        -- Copy constants
        class_uid = OCSF_CONSTANTS.class_uid,
        class_name = OCSF_CONSTANTS.class_name,
        category_uid = OCSF_CONSTANTS.category_uid,
        category_name = OCSF_CONSTANTS.category_name,
        activity_id = OCSF_CONSTANTS.activity_id,
        type_uid = OCSF_CONSTANTS.type_uid,
        type_name = OCSF_CONSTANTS.type_name
    }

    -- Process timestamp with validation
    output.time = parse_timestamp(unmapped.timestamp)

    -- Safe field mappings with validation
    if unmapped.hostname then
        output.src_endpoint = {hostname = unmapped.hostname}
    end

    if unmapped.operation then
        output.activity_name = unmapped.operation
    end

    -- Normalize status field
    output.status = normalize_status(unmapped.result)

    -- Actor information
    if unmapped.role or unmapped.user then
        output.actor = {
            user = {
                name = unmapped.role or unmapped.user
            }
        }
    end

    -- Resource information
    if unmapped.resource_id or unmapped.secret_id then
        output.resource = {
            uid = unmapped.resource_id,
            name = unmapped.secret_id
        }
    end

    -- Additional fields with validation
    if unmapped.authenticator then
        output.auth_protocol = unmapped.authenticator
    end

    if unmapped.privileges then
        output.privileges = unmapped.privileges
    end

    if unmapped.message then
        output.message = unmapped.message
    end

    -- Final validation of required OCSF fields
    if not output.time then
        output.time = os_time() * 1000
    end

    if not output.activity_name then
        output.activity_name = "Logon"
    end

    return output
end