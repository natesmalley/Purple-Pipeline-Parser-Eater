-- SentinelOne Parser: leef_template_logs-latest 
-- OCSF Class: Generic Event (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:04:19.177135

-- Pre-compile patterns for better performance
local timestamp_pattern = "^(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)%w+"
local key_pattern = "[%w]+"

-- Cached functions for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_match = string.match
local string_format = string.format

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local vars
    local output = {
        class_uid = 1001,
        class_name = "Generic Event", 
        category_uid = 1,
        category_name = "Generic Activity",
        activity_id = 1,
        type_uid = 100101,
        metadata = {
            version = "1.0.0",
            product = {
                vendor_name = "vendor",
                name = "vendor"
            }
        }
    }

    -- Timestamp transformation with validation
    if record.timestamp then
        local y,m,d,h,min,s = string_match(record.timestamp, timestamp_pattern)
        if y and m and d and h and min and s then
            -- Convert to UNIX milliseconds
            local ts = os_time({
                year = tonumber(y),
                month = tonumber(m),
                day = tonumber(d),
                hour = tonumber(h),
                min = tonumber(min),
                sec = tonumber(s)
            })
            output.time = ts * 1000
        end
    end

    -- Hostname mapping with sanitization
    if record.host then
        output.hostname = string_format("%s", record.host)
    end

    -- Key-value metadata extraction
    local metadata = {}
    for k,v in pairs(record) do
        if string_match(k, key_pattern) then
            metadata[k] = v
        end
    end
    output.metadata.raw_event = metadata

    -- Validation of required fields
    if not output.time then
        output.time = os_time() * 1000
    end

    if not output.hostname then
        output.hostname = "unknown"
    end

    -- Error checking before return
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    return output
end

-- Cache common error messages
local ERROR_MESSAGES = {
    invalid_input = "Invalid input record",
    missing_required = "Missing required fields",
    invalid_timestamp = "Invalid timestamp format"
}

-- Test function
function test()
    local test_cases = {
        {
            input = {
                timestamp = "2025-10-13T12:30:45UTC",
                host = "testhost",
                field1 = "value1"
            },
            expected = true
        },
        {
            input = nil,
            expected = false
        },
        {
            input = {},
            expected = true
        }
    }

    for i, test in ipairs(test_cases) do
        local result, err = transform(test.input)
        if test.expected then
            assert(result, string_format("Test %d failed: %s", i, err or ""))
        else
            assert(not result, string_format("Test %d should have failed", i))
        end
    end
end