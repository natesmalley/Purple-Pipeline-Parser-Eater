-- SentinelOne Parser: mail_server_logs-latest 
-- OCSF Class: System Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:04:38.438834

-- Pre-compile patterns for performance
local TIMESTAMP_PATTERN = "^[A-Za-z]+%s+%d{1,2} [%d:]+"
local PST_OFFSET = -28800 -- PST timezone offset in seconds

-- Local helper functions for performance
local function validate_timestamp(ts)
    if not ts then return nil end
    return os.time({
        year = os.date("%Y"),
        month = os.date("%m"), 
        day = os.date("%d"),
        hour = ts:match("%d+:%d+"):match("%d+"),
        min = ts:match(":%d+"):match("%d+")
    }) * 1000 + PST_OFFSET
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local vars
    local output = {
        class_uid = 1001,
        class_name = "System Activity", 
        category_uid = 1,
        category_name = "System",
        activity_id = 1,
        type_uid = 100101,
        metadata = {
            version = "1.0.0",
            product = {
                name = "Mail Server",
                vendor_name = "Generic"
            }
        }
    }

    -- Timestamp transformation with validation
    if record.timestamp then
        local ts = validate_timestamp(record.timestamp)
        if ts then
            output.time = ts
        else
            output.time = os.time() * 1000 -- Fallback to current time
        end
    end

    -- Optimized field mappings using local references
    local host = record.host
    if host then
        output.hostname = host
        output.observer = {hostname = host}
    end

    -- Service name mapping with validation
    local service = record.service
    if service and type(service) == "string" then
        output.service_name = service
    end

    -- Process ID casting with error handling
    local ps_id = record.ps_id
    if ps_id then
        local pid = tonumber(ps_id)
        if pid then
            output.process_id = pid
        end
    end

    -- Message field mapping with sanitization
    local details = record.details
    if details and type(details) == "string" then
        output.message = details:gsub("[^%g%s]", "") -- Remove control chars
    end

    -- Required field validation
    if not output.time then
        output.time = os.time() * 1000
    end

    -- Enrich with parsing metadata
    output.metadata.parser = {
        name = "mail_server_logs-latest",
        version = "1.0.0"
    }

    return output
end

-- Error handling wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string.format("Transform error: %s", result)
    end
    return result
end

-- Built-in test cases
local function run_tests()
    local test_cases = {
        {
            input = {
                timestamp = "Oct 13 14:23:11",
                host = "mailserver1",
                service = "postfix",
                ps_id = "1234",
                details = "Mail delivery successful"
            },
            expected_class_uid = 1001
        },
        {
            input = nil,
            expected_error = "Invalid input record"
        },
        {
            input = {},
            expected_class_uid = 1001
        }
    }

    for i, test in ipairs(test_cases) do
        local result = safe_transform(test.input)
        -- Test validation logic here
    end
end