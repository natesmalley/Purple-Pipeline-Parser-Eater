--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: wiz_cloud-latest
  Generated: 2025-10-13T12:39:08.677558
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: wiz_cloud-latest
-- OCSF Class: Cloud Security (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:04:58.860365

-- Pre-declare locals for performance optimization
local type = type
local tonumber = tonumber
local os_time = os.time
local string_match = string.match
local ISO8601_PATTERN = "(%d+)%-(%d+)%-(%d+)T(%d+):(%d+):(%d+)%.?(%d*)"

-- Utility functions
local function validate_timestamp(ts)
    if not ts then return nil end
    -- First try direct conversion
    local num = tonumber(ts)
    if num then return num end
    
    -- Try ISO8601 parsing
    local y,m,d,h,min,s,ms = string_match(ts, ISO8601_PATTERN)
    if y then
        -- Convert to epoch milliseconds
        local time = os.time({year=y, month=m, day=d, hour=h, min=min, sec=s})
        return time * 1000 + (tonumber(ms) or 0)
    end
    return nil
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure with local reference
    local output = {
        -- Metadata fields
        class_uid = 1001,
        class_name = "Cloud Security",
        category_uid = 1,
        category_name = "Cloud Infrastructure",
        activity_id = 1,
        type_uid = 100101,
        
        -- Product metadata
        metadata = {
            product = {
                name = "Cloud Security",
                vendor_name = "Wiz",
                version = "1.0.0"
            }
        }
    }

    -- Extract unmapped fields safely
    local unmapped = record.unmapped
    if type(unmapped) == "table" then
        -- Process timestamp with validation
        if unmapped.timestamp then
            local validated_time = validate_timestamp(unmapped.timestamp)
            if validated_time then
                output.time = validated_time
            else
                output.time = os_time() * 1000 -- Fallback to current time
                output.parsing_error = "Invalid timestamp format"
            end
        end

        -- Additional field mappings can be added here
    end

    -- Ensure required fields are present
    if not output.time then
        output.time = os_time() * 1000
    end

    -- Final validation
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    return output
end

-- Error handling wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string.format("Transform error: %s", result)
    end
    return result
end