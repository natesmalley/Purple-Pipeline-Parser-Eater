-- SentinelOne Parser: isc_bind-latest
-- OCSF Class: DNS Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:02:35.163848

-- Pre-declare locals for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_format = string.format

-- Validation constants
local REQUIRED_FIELDS = {
    "unmapped"
}

-- Error messages
local ERROR_MESSAGES = {
    invalid_input = "Invalid input record",
    missing_required = "Missing required field: %s",
    invalid_timestamp = "Invalid timestamp format"
}

-- ISO8601 to epoch converter with caching
local timestamp_cache = {}
local function iso8601_to_epoch(timestamp)
    -- Return cached value if exists
    if timestamp_cache[timestamp] then
        return timestamp_cache[timestamp]
    end
    
    -- Basic validation
    if type(timestamp) ~= "string" then
        return nil
    end

    -- Convert to epoch
    local epoch = tonumber(timestamp)
    if epoch then
        timestamp_cache[timestamp] = epoch
        return epoch
    end

    return nil
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, ERROR_MESSAGES.invalid_input
    end

    -- Validate required fields
    for _, field in ipairs(REQUIRED_FIELDS) do
        if not record[field] then
            return nil, string_format(ERROR_MESSAGES.missing_required, field)
        end
    end

    -- Initialize OCSF-compliant output structure
    local output = {
        -- Metadata
        class_uid = 1001,
        class_name = "DNS Activity", 
        category_uid = 1,
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = 100101,
        
        -- Source metadata
        metadata = {
            product = {
                name = "BIND DNS",
                vendor_name = "ISC"
            },
            version = "1.0.0"
        }
    }

    -- Timestamp transformation with validation
    if record.unmapped and record.unmapped.timestamp then
        local epoch = iso8601_to_epoch(record.unmapped.timestamp)
        if epoch then
            output.time = epoch
        else
            return nil, ERROR_MESSAGES.invalid_timestamp
        end
    else
        -- Default to current time if no timestamp
        output.time = os_time() * 1000
    end

    -- DNS specific field mappings
    if record.unmapped then
        -- Add additional DNS field mappings here
        -- Using local references for better performance
        local unmapped = record.unmapped
        
        -- Example DNS fields (extend based on actual data)
        if unmapped.query then
            output.query = unmapped.query
        end
        
        if unmapped.response then
            output.response = unmapped.response
        end
    end

    -- Final validation
    if not output.time or output.time <= 0 then
        return nil, ERROR_MESSAGES.invalid_timestamp
    end

    return output
end

-- Cache cleanup function (call periodically)
local function cleanup_cache()
    timestamp_cache = {}
end

-- Test helper function
local function run_tests()
    -- Test 1: Valid input
    local test1 = transform({
        unmapped = {
            timestamp = "1634145600",
            query = "example.com"
        }
    })
    assert(test1 and test1.class_uid == 1001)

    -- Test 2: Invalid input
    local test2 = transform(nil)
    assert(not test2)

    -- Test 3: Missing required field
    local test3 = transform({})
    assert(not test3)
end