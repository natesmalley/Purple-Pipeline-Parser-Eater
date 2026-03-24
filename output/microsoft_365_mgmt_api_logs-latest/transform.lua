-- SentinelOne Parser: microsoft_365_mgmt_api_logs-latest 
-- OCSF Class: System Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:06:09.363724

-- Pre-declare locals for performance
local type = type
local pairs = pairs
local os_time = os.time
local string_format = string.format

-- Validation helper functions
local function validate_record(record)
    if not record or type(record) ~= "table" then
        return false, "Invalid input record"
    end
    return true
end

local function validate_required_fields(output)
    if not output.class_uid or output.class_uid == 0 then
        return false, "Missing required field: class_uid"
    end
    if not output.category_uid then
        return false, "Missing required field: category_uid"
    end
    return true
end

function transform(record)
    -- Input validation with early return
    local valid, err = validate_record(record)
    if not valid then
        return nil, err
    end

    -- Initialize OCSF-compliant output structure with local reference
    local output = {
        -- Required OCSF fields
        class_uid = 1001,
        class_name = "System Activity",
        category_uid = 1, 
        category_name = "System",
        activity_id = 1,
        type_uid = 100101,
        
        -- Metadata
        observability = {
            version = "1.0.0",
            parser_id = "microsoft_365_mgmt_api_logs-latest"
        }
    }

    -- Performance-optimized field transformations
    local success, transform_err = pcall(function()
        -- Copy raw_365_event to event_base if present
        if record.raw_365_event then
            output.event_base = record.raw_365_event
            
            -- Extract additional metadata if available
            if type(record.raw_365_event) == "table" then
                output.metadata = {
                    source = "Microsoft 365 Management API",
                    vendor = "Microsoft",
                    product = "Microsoft 365"
                }
            end
        end

        -- Add timestamp if not present
        if not output.time then
            output.time = os_time() * 1000 -- Convert to milliseconds
        end
    end)

    if not success then
        return nil, string_format("Transform error: %s", transform_err)
    end

    -- Final validation
    local valid_fields, validation_err = validate_required_fields(output)
    if not valid_fields then
        return nil, validation_err
    end

    return output
end

-- Error handling wrapper for production use
function safe_transform(record)
    local success, result, err = pcall(transform, record)
    if not success then
        return nil, string_format("Runtime error: %s", result)
    end
    return result, err
end