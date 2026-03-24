--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: spam_detection_logs-latest
  Generated: 2025-10-13T11:51:26.196021
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: spam_detection_logs-latest 
-- OCSF Class: Application Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T11:13:11.871584

-- Pre-declare locals for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_format = string.format

-- Constant definitions
local CLASS_UID = 1001
local CATEGORY_UID = 1

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize output structure with pre-allocated fields
    local output = {
        class_uid = CLASS_UID,
        class_name = "Application Activity", 
        category_uid = CATEGORY_UID,
        category_name = "Application",
        activity_id = 1,
        type_uid = 100101,
        resource = {} -- Pre-allocate resource table
    }

    -- Safe number conversion helper
    local function safe_number(val)
        if not val then return nil end
        local num = tonumber(val)
        return num and num >= 0 and num or nil
    end

    -- Optimized field transformations
    local duration = safe_number(record.duration)
    if duration then
        output.duration = duration
    end

    -- Memory metrics processing
    local mem_size = safe_number(record.mem_size)
    local max_mem = safe_number(record.max_mem_used)
    
    if mem_size then
        output.resource.memory_allocated = mem_size
    end
    
    if max_mem then
        output.resource.memory_used = max_mem
    end

    -- Error status detection
    if record.error or record.exception then
        output.status = "FAILURE"
        output.status_detail = string_format("Error: %s", 
            record.error or record.exception or "Unknown error")
    else
        output.status = "SUCCESS"
    end

    -- Timestamp handling
    output.time = record.timestamp or (os_time() * 1000)

    -- Metadata enrichment
    output.metadata = {
        product = {
            name = "Spam Detection Service",
            vendor_name = "Generic"
        },
        version = record.version or "0.26"
    }

    -- Final validation
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    return output
end

-- Error wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end