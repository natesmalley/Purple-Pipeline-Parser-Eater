-- SentinelOne Parser: microsoft_windows_eventlog-latest
-- OCSF Class: Group Management (3005)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:07:15.031897

-- Pre-compile patterns for performance
local patterns = {
    security_id = "Security ID:%s*([^%s]+)",
    account_name = "Account Name:%s*([^%s]+)",
    group_name = "Group Name:%s*([^%s]+)"
}

-- Cache common string operations
local match = string.match
local format = string.format
local time = os.time

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Extract event description
    local description = record.event_description
    if not description or type(description) ~= "string" then
        return nil, "Missing or invalid event description"
    end

    -- Initialize OCSF-compliant output structure
    local output = {
        class_uid = 3005,
        class_name = "Group Management",
        category_uid = 3,
        category_name = "Identity & Access Management",
        activity_id = 1,
        type_uid = 300501,
        actor = {},
        target = {
            group = {}
        },
        metadata = {
            version = "1.0.0",
            product = {
                name = "Windows Event Log",
                vendor_name = "Microsoft"
            }
        }
    }

    -- Extract fields using optimized pattern matching
    local security_id = match(description, patterns.security_id)
    local account_name = match(description, patterns.account_name) 
    local group_name = match(description, patterns.group_name)

    -- Populate actor fields if found
    if security_id then
        output.actor.user_id = security_id
    end
    if account_name then
        output.actor.user_name = account_name
    end

    -- Populate target group fields
    if group_name then
        output.target.group.name = group_name
    end

    -- Add timestamp if not present
    if not output.time then
        output.time = time() * 1000
    end

    -- Validate required OCSF fields
    if not output.actor.user_id or not output.target.group.name then
        return nil, "Missing required fields"
    end

    -- Add status
    output.status = "success"
    output.status_detail = "Group membership modified"

    return output
end

-- Error handling wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, format("Transform error: %s", result)
    end
    return result
end

-- Batch processing support
function transform_batch(records)
    local results = {}
    local errors = {}
    
    for i, record in ipairs(records) do
        local result, err = safe_transform(record)
        if result then
            results[#results + 1] = result
        else
            errors[#errors + 1] = {
                index = i,
                error = err
            }
        end
    end
    
    return results, errors
end