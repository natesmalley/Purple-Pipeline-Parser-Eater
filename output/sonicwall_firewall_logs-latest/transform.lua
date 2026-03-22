--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: sonicwall_firewall_logs-latest
  Generated: 2025-10-13T11:50:58.591322
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: sonicwall_firewall_logs-latest 
-- OCSF Class: Network Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T11:13:10.861621

-- Pre-compile patterns for performance
local TIMESTAMP_PATTERN = "^(%d%d%d%d%-%d%d%-%d%d%s+%d%d:%d%d:%d%d)"
local SEQ_PATTERN = "^<(%d+)>"

-- Cached functions for performance
local tonumber = tonumber
local type = type
local os_time = os.time
local string_match = string.match
local string_format = string.format

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure with local vars
    local output = {
        class_uid = 1001,
        class_name = "Network Activity", 
        category_uid = 1,
        category_name = "Network & Systems Activity",
        activity_id = 1,
        type_uid = 100101,
        metadata = {},
        time = nil,
        observables = {}
    }

    -- Extract and validate timestamp
    local timestamp = record.timestamp
    if timestamp then
        local parsed_time = string_match(timestamp, TIMESTAMP_PATTERN)
        if parsed_time then
            output.time = os_time({
                year = tonumber(string_match(parsed_time, "(%d%d%d%d)")),
                month = tonumber(string_match(parsed_time, "%d%d%d%d%-(%d%d)")),
                day = tonumber(string_match(parsed_time, "%d%d%d%d%-%d%d%-(%d%d)")),
                hour = tonumber(string_match(parsed_time, "%d%d:(%d%d):")),
                min = tonumber(string_match(parsed_time, "%d%d:%d%d:(%d%d)")),
                sec = tonumber(string_match(parsed_time, "%d%d:%d%d:%d%d"))
            }) * 1000
        end
    end

    -- Extract sequence number with validation
    if record.seq then
        local seq_num = string_match(record.seq, SEQ_PATTERN)
        if seq_num then
            output.metadata.sequence = tonumber(seq_num)
        end
    end

    -- Copy identifier to metadata.name with sanitization
    if record.identifier then
        output.metadata.name = string_format("%s", record.identifier:gsub("[^%w%s%-_]", ""))
    end

    -- Add source metadata
    output.metadata.product = {
        name = "SonicWall Firewall",
        vendor_name = "SonicWall"
    }

    -- Validation and cleanup
    if not output.time then
        output.time = os_time() * 1000
    end

    if not output.metadata.sequence then
        output.metadata.sequence = 0
    end

    -- Final validation of required fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    return output
end

-- Error handler wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end

-- Batch processing optimization
function transform_batch(records)
    if not records or type(records) ~= "table" then
        return nil, "Invalid batch input"
    end

    local results = {}
    local errors = {}
    
    for i, record in ipairs(records) do
        local result, err = safe_transform(record)
        if result then
            results[#results + 1] = result
        else
            errors[#errors + 1] = {index = i, error = err}
        end
    end
    
    return results, errors
end