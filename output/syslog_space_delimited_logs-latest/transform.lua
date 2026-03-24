--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: syslog_space_delimited_logs-latest
  Generated: 2025-10-13T11:52:52.752247
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: syslog_space_delimited_logs-latest 
-- OCSF Class: Generic Event (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T11:13:41.920637

-- Pre-compile patterns for performance
local PATTERNS = {
    key = "^[%w_]+$",
    value = "^[%w%s%.%-_@]+$"
}

-- Cached references for performance
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

    -- Initialize OCSF-compliant output structure with local references
    local output = {
        class_uid = 1001,
        class_name = "Generic Event", 
        category_uid = 1,
        category_name = "Generic",
        activity_id = 1,
        type_uid = 100101,
        metadata = {},
        device = {},
        time = record.time or (os_time() * 1000)
    }

    -- Optimized field transformations using local references
    local device = output.device
    local metadata = output.metadata

    -- Device vendor mapping with validation
    if record.deviceVendor then
        local vendor = record.deviceVendor
        if string_match(vendor, PATTERNS.value) then
            device.vendor = vendor
        else
            metadata.vendor_parse_error = "Invalid vendor format"
        end
    end

    -- Device product mapping with validation
    if record.deviceProduct then
        local product = record.deviceProduct
        if string_match(product, PATTERNS.value) then
            device.product = product
        else
            metadata.product_parse_error = "Invalid product format"
        end
    end

    -- Severity casting with validation
    if record.severity then
        local severity = tonumber(record.severity)
        if severity and severity >= 0 and severity <= 10 then
            output.severity = severity
        else
            metadata.severity_parse_error = string_format(
                "Invalid severity value: %s", record.severity)
        end
    end

    -- Extension field processing with memory optimization
    if record.extension then
        local ext = record.extension
        if type(ext) == "string" then
            -- Process extension fields efficiently
            for k, v in string.gmatch(ext, "(%w+)=([^%s]+)") do
                if string_match(k, PATTERNS.key) then
                    metadata[k] = v
                end
            end
        end
    end

    -- Validation of required OCSF fields
    if not device.vendor and not device.product then
        return nil, "Missing required device fields"
    end

    -- Add processing metadata
    metadata.parser_version = "1.0.0"
    metadata.processed_time = os_time() * 1000

    return output
end

-- Error recovery function
local function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end

-- Batch processing optimization
function transform_batch(records)
    local results = {}
    local errors = {}
    
    for i, record in ipairs(records) do
        local result, err = safe_transform(record)
        results[i] = result
        if err then
            errors[i] = err
        end
    end
    
    return results, errors
end