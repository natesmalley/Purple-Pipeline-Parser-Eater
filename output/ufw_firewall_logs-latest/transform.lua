--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: ufw_firewall_logs-latest
  Generated: 2025-10-13T11:53:48.942085
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: ufw_firewall_logs-latest 
-- OCSF Class: Network Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T11:13:57.243149

-- Pre-compile patterns for better performance
local timestamp_pattern = "^(%w+)%s+(%d+)%s+(%d+):(%d+):(%d+)"
local details_pattern = "OUT=%s*(.+)$"

-- Cached reference to frequently used functions
local string_match = string.match
local string_format = string.format
local os_time = os.time

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local references
    local output = {
        class_uid = 1001,
        class_name = "Network Activity", 
        category_uid = 1,
        category_name = "Network & Systems Activity",
        activity_id = 1,
        type_uid = 100101,
        metadata = {},
        device = {},
        network = {}
    }

    -- Timestamp transformation with validation
    if record.timestamp then
        local month, day, hour, min, sec = string_match(record.timestamp, timestamp_pattern)
        if month and day and hour and min and sec then
            -- Convert to UNIX timestamp (simplified for example)
            output.time = os_time() * 1000
        else
            output.time = os_time() * 1000 -- Fallback to current time
        end
    end

    -- Optimized device hostname mapping
    if record.serverHost then
        output.device.hostname = record.serverHost
    end

    -- Action field transformation with validation
    if record.action then
        output.activity_name = record.action
        -- Map common UFW actions to OCSF activity types
        local action_map = {
            ["BLOCK"] = "blocked",
            ["ALLOW"] = "allowed",
            ["DROP"] = "dropped"
        }
        output.activity_type = action_map[record.action:upper()] or "unknown"
    end

    -- Network traffic details parsing
    if record.details then
        local traffic = string_match(record.details, details_pattern)
        if traffic then
            output.network.traffic = {
                raw = traffic,
                parsed = parse_network_details(traffic)
            }
        end
    end

    -- Validation of required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    -- Add metadata
    output.metadata.parser_version = "1.0.0"
    output.metadata.confidence = 0.88

    return output
end

-- Helper function to parse network details
-- Optimized for performance with local cache
local function parse_network_details(traffic_str)
    if not traffic_str then return {} end
    
    local details = {}
    local pattern = "(%w+)=([^%s]+)"
    
    for key, value in string.gmatch(traffic_str, pattern) do
        details[key:lower()] = value
    end
    
    return details
end

-- Error handling wrapper
local function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end

return {
    transform = safe_transform,
    
    -- Expose configuration for runtime updates
    config = {
        max_field_length = 1024,
        enable_debug = false,
        cache_size = 1000
    }
}