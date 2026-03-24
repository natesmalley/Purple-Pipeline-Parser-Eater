-- SentinelOne Parser: microsoft_365_collaboration-latest 
-- OCSF Class: File Activity (6001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:05:50.898730

-- Localize functions for performance
local type = type
local pairs = pairs
local os_time = os.time
local string_format = string.format

-- Validation constants
local REQUIRED_FIELDS = {
    "activity_events"
}

-- Error messages
local ERROR_MESSAGES = {
    invalid_input = "Invalid input record",
    missing_required = "Missing required field: %s",
    invalid_class = "Invalid class_uid"
}

-- Field validation helper
local function validate_field(record, field)
    return record[field] ~= nil and record[field] ~= ""
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, ERROR_MESSAGES.invalid_input
    end

    -- Initialize OCSF-compliant output structure with local table
    local output = {
        class_uid = 6001,
        class_name = "File Activity", 
        category_uid = 6,
        category_name = "Resource Activity",
        activity_id = 1,
        type_uid = 600101,
        metadata = {
            version = "1.0.0",
            product = {
                name = "Microsoft 365",
                vendor = "Microsoft"
            }
        }
    }

    -- Validate required fields
    for _, field in pairs(REQUIRED_FIELDS) do
        if not validate_field(record, field) then
            return nil, string_format(ERROR_MESSAGES.missing_required, field)
        end
    end

    -- Performance-optimized field transformations
    -- Using local variables for field access
    local activity_events = record.activity_events
    if activity_events then
        output.activity_name = activity_events
        
        -- Add activity classification
        output.activity_id = 1 -- Default activity ID
        output.type_name = "File Activity"
    end

    -- Add source context
    output.src = {
        product = {
            name = "Microsoft 365 Collaboration",
            feature = {
                name = "SharePoint/OneDrive"
            }
        }
    }

    -- Add timestamp if not present
    if not output.time then
        output.time = os_time() * 1000 -- Convert to milliseconds
    end

    -- Final validation
    if not output.class_uid or output.class_uid == 0 then
        return nil, ERROR_MESSAGES.invalid_class
    end

    -- Success - return transformed record
    return output
end

-- Error handling wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, "Transform error: " .. tostring(result)
    end
    return result
end

-- Cache for frequent operations
local field_cache = {}

-- Batch processing helper
function transform_batch(records)
    local results = {}
    local errors = {}
    
    for i, record in pairs(records) do
        local result, err = safe_transform(record)
        if result then
            results[i] = result
        else
            errors[i] = err
        end
    end
    
    return results, errors
end