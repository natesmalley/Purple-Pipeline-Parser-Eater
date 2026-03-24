-- SentinelOne Parser: microsoft_eventhub_defender_email_logs-latest 
-- OCSF Class: Email Security (6001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:06:37.403439

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

local function validate_email_event(event)
    if not event or type(event) ~= "table" then
        return false
    end
    -- Add specific email event validation logic here
    return true
end

function transform(record)
    -- Input validation with detailed error message
    local valid, err = validate_record(record)
    if not valid then
        return nil, err or "Record validation failed"
    end

    -- Initialize OCSF-compliant output structure with local reference
    local output = {
        -- Required OCSF fields
        class_uid = 6001,
        class_name = "Email Security", 
        category_uid = 6,
        category_name = "Communications Security",
        activity_id = 1,
        type_uid = 600101,
        time = record.time or (os_time() * 1000),
        metadata = {
            version = "1.0.0",
            product = {
                name = "Microsoft Defender for Email",
                vendor_name = "Microsoft"
            }
        }
    }

    -- Optimized email events transformation
    if record.email_events then
        -- Create local reference to avoid repeated table lookups
        local email_events = record.email_events
        
        -- Validate email events before processing
        if validate_email_event(email_events) then
            output.email_events = email_events
            
            -- Add optional enrichment if available
            if email_events.sender then
                output.src_endpoint = {
                    email = email_events.sender
                }
            end
            
            if email_events.recipients then
                output.dst_endpoint = {
                    email = email_events.recipients
                }
            end
        end
    end

    -- Final validation before return
    if not output.email_events then
        return nil, "Missing required email events data"
    end

    -- Add processing metadata
    output.observability = {
        processor_version = "1.0.0",
        processing_time = os_time()
    }

    return output
end

-- Error handling wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end

-- Built-in test cases
local function run_tests()
    local test_cases = {
        {
            input = {
                email_events = {
                    sender = "sender@example.com",
                    recipients = {"recipient@example.com"},
                    subject = "Test Email"
                }
            },
            expected = true
        },
        {
            input = nil,
            expected = false
        },
        {
            input = {},
            expected = false
        }
    }

    for i, test in ipairs(test_cases) do
        local result = safe_transform(test.input)
        print(string_format("Test %d: %s", i, result and "PASS" or "FAIL"))
    end
end