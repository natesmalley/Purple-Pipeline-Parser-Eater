-- SentinelOne Parser: okta_ocsf_logs-latest 
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:07:51.919730

-- Pre-declare locals for performance
local type = type
local os_time = os.time
local string_format = string.format
local error_msgs = {
    invalid_input = "Invalid input record",
    missing_class = "Missing required class_uid",
    invalid_event = "Invalid event type"
}

-- Validation helper functions
local function validate_record(record)
    return record and type(record) == "table"
end

local function validate_event_type(event_type)
    return event_type and type(event_type) == "string" and #event_type > 0
end

function transform(record)
    -- Fast input validation
    if not validate_record(record) then
        return nil, error_msgs.invalid_input
    end

    -- Initialize OCSF output with static fields
    local output = {
        -- OCSF Classification 
        class_uid = 3002,
        class_name = "Authentication",
        category_uid = 3,
        category_name = "Identity & Access Management",
        activity_id = 1,
        type_uid = 300201,
        
        -- Metadata
        version = "1.0.0",
        time = record.time or (os_time() * 1000)
    }

    -- Optimized field transformations
    if record.okta_event then
        if validate_event_type(record.okta_event) then
            output.event_type = record.okta_event
        else
            return nil, error_msgs.invalid_event
        end
    end

    -- Add optional fields if present
    if record.actor then
        output.actor = {
            user = {
                name = record.actor.name,
                uid = record.actor.id
            }
        }
    end

    -- Enrich with Okta-specific metadata
    output.metadata = {
        product = {
            name = "Okta Identity Cloud",
            vendor = "Okta"
        },
        version = "1.0.0"
    }

    -- Final validation
    if not output.class_uid or output.class_uid == 0 then
        return nil, error_msgs.missing_class
    end

    return output
end

-- Performance test helper
local function run_performance_test()
    local start = os_time()
    local count = 0
    local test_record = {
        okta_event = "user.session.start",
        actor = {
            name = "test_user",
            id = "user123"
        }
    }
    
    for i = 1, 10000 do
        local result = transform(test_record)
        if result then count = count + 1 end
    end
    
    return string_format("Processed %d records in %d seconds", 
                        count, os_time() - start)
end