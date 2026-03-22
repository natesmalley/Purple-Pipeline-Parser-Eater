-- SentinelOne Parser: cisco_umbrella_logs-latest 
-- OCSF Class: Network Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:56:28.841600

-- Pre-compile patterns for performance
local timestamp_pattern = "^(%d%d%d%d)%-(%d%d)%-(%d%d) (%d%d):(%d%d):(%d%d)$"

-- Cached reference to frequently used functions
local type = type
local tonumber = tonumber
local os_time = os.time
local string_match = string.match

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure with local references
    local output = {
        class_uid = 1001,
        class_name = "Network Activity", 
        category_uid = 1,
        category_name = "Network & Systems Activity",
        activity_id = 1,
        type_uid = 100101,
        src_endpoint = {},
        metadata = {
            product = {
                name = "Cisco Umbrella",
                vendor_name = "Cisco"
            }
        }
    }

    -- Timestamp processing with error handling
    if record.timestamp then
        local year, month, day, hour, min, sec = string_match(record.timestamp, timestamp_pattern)
        if year then
            -- Convert timestamp components to epoch milliseconds
            local ts = os_time({
                year = tonumber(year),
                month = tonumber(month),
                day = tonumber(day),
                hour = tonumber(hour),
                min = tonumber(min),
                sec = tonumber(sec)
            })
            output.time = ts * 1000 -- Convert to milliseconds
        end
    end

    -- Optimized field mappings using local references
    if record.InternalClientIP then
        output.src_endpoint.ip = record.InternalClientIP
    end

    if record.Action then
        output.activity_name = record.Action
        -- Map common Umbrella actions to OCSF activity_id
        local action_map = {
            ["blocked"] = 2,
            ["allowed"] = 1,
            ["proxied"] = 3
        }
        output.activity_id = action_map[record.Action:lower()] or 1
    end

    -- Determine log type and set specific fields
    if record.QueryType then
        -- DNS Log specific processing
        output.type_name = "DNS Query"
        output.network = {
            dns = {
                query = record.Domain,
                query_type = record.QueryType
            }
        }
    elseif record.url then
        -- Proxy Log specific processing
        output.type_name = "HTTP Request"
        output.http = {
            request = {
                url = record.url,
                method = record.RequestMethod
            },
            response = {
                status_code = tonumber(record.StatusCode)
            }
        }
    end

    -- Add categories if present
    if record.Categories then
        output.security = {
            categories = record.Categories:split(",")
        }
    end

    -- Validation of required fields
    if not output.time then
        output.time = os_time() * 1000
    end

    if not output.activity_name then
        output.activity_name = "unknown"
    end

    return output
end

-- Helper function for string splitting
local function split(str, sep)
    if not str then return {} end
    local result = {}
    for match in (str..sep):gmatch("(.-)"..sep) do
        table.insert(result, match)
    end
    return result
end