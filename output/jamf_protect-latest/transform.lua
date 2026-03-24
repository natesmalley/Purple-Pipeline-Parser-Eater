-- Jamf Protect Parser (jamf_protect-latest)
-- OCSF Class: Security Finding (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:02:37.932717

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

-- Initialize nested table helper
local function init_nested_table(parent, key)
    if not parent[key] then
        parent[key] = {}
    end
    return parent[key]
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure with local reference
    local output = {
        class_uid = 1001,
        class_name = "Security Finding", 
        category_uid = 1,
        category_name = "Security Control",
        activity_id = 1,
        type_uid = 100101,
        metadata = {
            product = {
                name = "Jamf Protect",
                vendor = "Jamf"
            },
            version = "1.0"
        }
    }

    -- Initialize nested objects
    local finding = init_nested_table(output, "finding")
    local actor = init_nested_table(output, "actor")
    local device = init_nested_table(output, "device")
    local process = init_nested_table(output, "process")
    local file = init_nested_table(output, "file")
    
    -- Optimized field mapping with validation
    if validate_string(record.eventType) then
        finding.title = record.eventType
    end

    if validate_string(record.user) then
        if not actor.user then actor.user = {} end
        actor.user.name = record.user
    end

    if validate_string(record.computerId) then
        device.uid = record.computerId
    end

    if validate_string(record.processName) then
        if not process.file then process.file = {} end
        process.file.path = record.processName
    end

    if validate_string(record.sha256) then
        if not file.hashes then file.hashes = {} end
        file.hashes.sha256 = record.sha256
    end

    -- Add message if present
    if validate_string(record.message) then
        output.message = record.message
    end

    -- Add verdict/disposition if present
    if validate_string(record.verdict) then
        output.disposition = record.verdict
    end

    -- Set timestamp
    output.time = record.timestamp or (os_time() * 1000)

    -- Validate required fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Missing required class_uid"
    end

    -- Remove empty nested tables
    for k,v in pairs(output) do
        if type(v) == "table" and next(v) == nil then
            output[k] = nil
        end
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