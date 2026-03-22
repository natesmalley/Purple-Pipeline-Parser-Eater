--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: veeam_backup-latest
  Generated: 2025-10-13T12:35:58.063087
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: veeam_backup-latest 
-- OCSF Class: System Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:04:24.255082

-- Lookup tables for better performance
local SEVERITY_MAP = {
    Success = {id = 1, name = "Create"},
    Warning = {id = 2, name = "Update"}, 
    Error = {id = 99, name = "Other"}
}

local SEVERITY_ID_MAP = {
    Success = 1,
    Warning = 2,
    Error = 4
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local vars
    local output = {
        -- Constants defined once
        class_uid = 1001,
        class_name = "System Activity",
        category_uid = 1, 
        category_name = "System",
        type_uid = 100199
    }

    -- Timestamp handling with validation
    local timestamp = record.unmapped and record.unmapped.timestamp
    if timestamp then
        -- Convert ISO8601 to epoch seconds
        local year, month, day, hour, min, sec = timestamp:match(
            "(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)"
        )
        if year then
            output.time = os.time({
                year = tonumber(year),
                month = tonumber(month),
                day = tonumber(day),
                hour = tonumber(hour),
                min = tonumber(min),
                sec = tonumber(sec)
            })
        end
    end

    -- Efficient field mapping using local references
    local unmapped = record.unmapped
    if unmapped then
        -- Direct field mappings
        output.job = {
            uid = unmapped.JobID,
            name = unmapped.JobName
        }
        output.session = {
            uid = unmapped.JobSessionID
        }
        output.status_id = unmapped.JobResult
        output.message = unmapped.Description
        output.warning_count = tonumber(unmapped.WarningCount) or 0
        output.resource = {
            name = unmapped.AffectedObjects,
            count = tonumber(unmapped.ObjectsProcessed) or 0,
            size = tonumber(unmapped.TotalSize) or 0
        }
        output.duration = tonumber(unmapped.Duration) or 0

        -- Severity mapping using lookup table
        local severity = unmapped.severity
        if severity then
            local severity_map = SEVERITY_MAP[severity]
            if severity_map then
                output.activity_id = severity_map.id
                output.activity_name = severity_map.name
                output.severity_id = SEVERITY_ID_MAP[severity]
            end
        end
    end

    -- Validation of required fields
    if not output.time then
        output.time = os.time()
    end
    if not output.severity_id then
        output.severity_id = 1 -- Default to lowest severity
    end

    -- Data type validation
    output.warning_count = tonumber(output.warning_count) or 0
    output.duration = tonumber(output.duration) or 0
    
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