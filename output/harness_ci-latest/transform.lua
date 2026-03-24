-- SentinelOne Parser: harness_ci-latest
-- OCSF Class: Job Activity (6003)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:00:53.619569

-- Pre-compile status mapping patterns for performance
local STATUS_PATTERNS = {
    ["^STARTED$"] = {activity_id = 1, activity_name = "Start", status_id = 1, status = "Success"},
    ["^RUNNING$"] = {activity_id = 1, activity_name = "Start", status_id = 1, status = "Success"},
    ["^SUCCEEDED$"] = {activity_id = 2, activity_name = "Complete", status_id = 1, status = "Success"},
    ["^FAILED$"] = {activity_id = 99, activity_name = "Other", status_id = 2, status = "Failure"},
    ["^CANCELLED$"] = {activity_id = 3, activity_name = "Cancel", status_id = 99, status = "Other"},
    ["^PAUSED$"] = {activity_id = 3, activity_name = "Cancel", status_id = 99, status = "Other"}
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local variables
    local output = {
        -- Static OCSF classification fields
        class_uid = 6003,
        class_name = "Job Activity", 
        category_uid = 6,
        category_name = "Application Activity",
        type_uid = 600301,
        severity_id = 1,
        severity = "Informational",

        -- Initialize nested tables
        job = {},
        actor = {
            user = {}
        }
    }

    -- Efficient field mapping with validation
    local function safe_copy(src_field, dest_field)
        if record[src_field] and record[src_field] ~= "" then
            output[dest_field] = record[src_field]
            return true
        end
        return false
    end

    -- Required field mappings
    safe_copy("timestamp", "time")
    safe_copy("pipeline_id", "job.name") 
    safe_copy("execution_id", "job.uid")
    safe_copy("trigger", "job.run_type")
    safe_copy("initiator", "actor.user.name")
    safe_copy("message", "message")

    -- Status mapping with pattern matching
    if record.status then
        local status = record.status:upper()
        for pattern, mapping in pairs(STATUS_PATTERNS) do
            if status:match(pattern) then
                output.activity_id = mapping.activity_id
                output.activity_name = mapping.activity_name
                output.status_id = mapping.status_id
                output.status = mapping.status
                output.status_detail = status
                break
            end
        end
    end

    -- Validation of required OCSF fields
    if not output.job.name then
        return nil, "Missing required field: job.name"
    end

    if not output.time then
        output.time = os.time() * 1000 -- Default to current time in ms
    end

    -- Add observables
    output.observables = {
        {
            name = output.actor.user.name,
            type = "User"
        },
        {
            name = output.job.name,
            type = "Other"
        },
        {
            name = output.job.uid,
            type = "Other"
        }
    }

    return output
end

-- Cache common string patterns
local VALIDATION_PATTERNS = {
    timestamp = "^%d+%.?%d*$",
    pipeline_id = "^[%w-_]+$"
}

-- Validation helper
local function validate_field(value, pattern)
    if not value then return false end
    return value:match(pattern) ~= nil
end