-- SentinelOne Parser: beyondtrust_passwordsafe_logs-latest 
-- OCSF Class: Access Activity (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:52:10.129310

-- Pre-declare locals for performance
local type = type
local pairs = pairs
local tonumber = tonumber
local os_time = os.time
local string_format = string.format

-- Validation constants
local REQUIRED_FIELDS = {
    "eventid",
    "eventname", 
    "sourceip",
    "user"
}

-- Field mapping cache for performance
local FIELD_MAPPINGS = {
    eventid = "access_activity.activity_id",
    eventname = "access_activity.activity_name", 
    sourceip = "src.ip.address",
    user = "user.name"
}

-- Helper function to safely get nested table values
local function get_nested_value(tbl, path)
    local current = tbl
    for segment in path:gmatch("[^%.]+") do
        if type(current) ~= "table" then return nil end
        current = current[segment]
    end
    return current
end

-- Helper function to safely set nested table values
local function set_nested_value(tbl, path, value)
    local current = tbl
    local segments = {}
    for segment in path:gmatch("[^%.]+") do
        segments[#segments + 1] = segment
    end
    
    for i=1, #segments-1 do
        local key = segments[i]
        current[key] = current[key] or {}
        current = current[key]
    end
    current[segments[#segments]] = value
end

function transform(record)
    -- Input validation with detailed error messages
    if not record then
        return nil, "Record is nil"
    end
    
    if type(record) ~= "table" then
        return nil, string_format("Expected table, got %s", type(record))
    end

    -- Initialize OCSF-compliant output structure with required fields
    local output = {
        class_uid = 3002,
        class_name = "Access Activity",
        category_uid = 3,
        category_name = "Identity & Access Management",
        metadata = {
            version = "1.0.0",
            product = {
                vendor_name = "BeyondTrust",
                name = "Password Safe"
            }
        },
        time = record.access_activity and record.access_activity.time or (os_time() * 1000)
    }

    -- Validate required fields exist
    local missing_fields = {}
    for _, field in ipairs(REQUIRED_FIELDS) do
        if not record[field] then
            missing_fields[#missing_fields + 1] = field
        end
    end
    
    if #missing_fields > 0 then
        return nil, string_format("Missing required fields: %s", table.concat(missing_fields, ", "))
    end

    -- Optimized field mapping using cached paths
    for source, target in pairs(FIELD_MAPPINGS) do
        local value = record[source]
        if value then
            set_nested_value(output, target, value)
        end
    end

    -- Additional field transformations and enrichment
    if record.severity then
        output.severity = tonumber(record.severity) or 0
    end

    if record.eventtype then
        output.type_uid = tonumber(record.eventtype) or 300201
    end

    -- Validate output meets OCSF requirements
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid in output"
    end

    if not output.time then
        output.time = os_time() * 1000
    end

    return output
end

-- Error handler wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end