-- SentinelOne Parser: cisco_umbrella-latest 
-- OCSF Class: Security Finding (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:56:28.844578

-- Pre-compile patterns for performance
local timestamp_pattern = "^(%d%d%d%d)-(%d%d)-(%d%d) (%d%d):(%d%d):(%d%d)$"

-- Cached reference to frequently used functions
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

    -- Initialize OCSF-compliant output with local references
    local output = {
        class_uid = 1001,
        class_name = "Security Finding", 
        category_uid = 1,
        category_name = "Security Control",
        activity_id = 1,
        type_uid = 100101,
        src_endpoint = {},
        metadata = {
            product = {
                name = "Cisco Umbrella",
                vendor = "Cisco"
            }
        }
    }

    -- Timestamp processing with validation
    if record.timestamp then
        local year, month, day, hour, min, sec = string_match(record.timestamp, timestamp_pattern)
        if year then
            -- Convert to UNIX milliseconds for OCSF compliance
            local ts = os_time({
                year = tonumber(year),
                month = tonumber(month),
                day = tonumber(day),
                hour = tonumber(hour),
                min = tonumber(min),
                sec = tonumber(sec)
            })
            output.time = ts * 1000
        end
    end

    -- Optimized field mappings using local references
    if record.Action then
        output.activity_name = record.Action
        -- Map common actions to OCSF activity IDs
        if record.Action == "blocked" then
            output.activity_id = 2
        elseif record.Action == "allowed" then
            output.activity_id = 1
        end
    end

    -- IP address handling with validation
    if record.InternalClientIP then
        output.src_endpoint.ip = record.InternalClientIP
        -- Optional IP validation could be added here
    end

    -- Additional field mappings based on log type
    if record.LogType == "proxylogs" then
        if record.url then
            output.http = {
                url = record.url,
                response_code = tonumber(record.StatusCode),
                request_method = record.RequestMethod
            }
        end
        if record.Categories then
            output.security_result = {
                category = record.Categories,
                action = record.Action
            }
        end
    end

    -- DNS specific fields
    if record.LogType == "dnslogs" then
        if record.Domain then
            output.dns = {
                query = record.Domain,
                response_code = tonumber(record.ResponseCode),
                query_type = record.QueryType
            }
        end
    end

    -- Validation of required OCSF fields
    if not output.time then
        output.time = os_time() * 1000
    end

    if not output.activity_name then
        output.activity_name = "unknown"
    end

    -- Error checking before return
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    return output
end