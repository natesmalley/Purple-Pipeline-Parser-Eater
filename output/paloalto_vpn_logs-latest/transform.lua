-- SentinelOne Parser: paloalto_vpn_logs-latest 
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:08:47.964461

-- Pre-declare locals for performance
local type = type
local os_time = os.time
local string_format = string.format
local error_msgs = {
    invalid_input = "Invalid input record",
    invalid_class = "Invalid class_uid",
    missing_required = "Missing required field: %s"
}

-- Validation helper functions
local function validate_record(record)
    if not record or type(record) ~= "table" then
        return false, error_msgs.invalid_input
    end
    return true
end

local function validate_string(value, field_name)
    if type(value) ~= "string" then
        return false, string_format(error_msgs.missing_required, field_name)
    end
    return true
end

function transform(record)
    -- Input validation with early return
    local valid, err = validate_record(record)
    if not valid then
        return nil, err
    end

    -- Initialize OCSF-compliant output structure with local references
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
                name = "PAN-OS",
                vendor_name = "Palo Alto Networks"
            }
        }
    }

    -- Performance-optimized field transformations
    local event_type = record.event_type
    if event_type then
        -- Validate event_type is string
        local valid, err = validate_string(event_type, "event_type")
        if valid then
            output.activity_name = event_type
        else
            -- Log warning but continue processing
            output.parse_warning = err
        end
    end

    -- Add additional VPN-specific fields if present
    if record.src_ip then
        output.src = {ip = record.src_ip}
    end
    
    if record.dst_ip then
        output.dst = {ip = record.dst_ip}
    end

    -- Add authentication status if present
    if record.status then
        output.status = string.lower(record.status)
    end

    -- Add timestamp handling with fallback
    output.time = record.time or (os_time() * 1000)

    -- Final validation
    if not output.class_uid or output.class_uid == 0 then
        return nil, error_msgs.invalid_class
    end

    return output
end

-- Cache common string patterns
local STRING_PATTERNS = {
    ipv4 = "^%d+%.%d+%.%d+%.%d+$",
    timestamp = "^%d+$"
}

-- Test helper function
local function run_tests()
    -- Test Case 1: Valid input
    local test1 = transform({
        event_type = "vpn_login",
        src_ip = "192.168.1.1",
        status = "success",
        time = 1634567890000
    })
    assert(test1.activity_name == "vpn_login")

    -- Test Case 2: Invalid input
    local test2, err2 = transform(nil)
    assert(test2 == nil and err2 == error_msgs.invalid_input)

    -- Test Case 3: Empty record
    local test3 = transform({})
    assert(test3.class_uid == 3002)
end

-- Uncomment to run tests
-- run_tests()