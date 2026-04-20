-- GitHub Audit Log to OCSF Process Activity Transformation
-- Maps GitHub audit events to OCSF Process Activity (class_uid=1007)

local CLASS_UID = 1007
local CATEGORY_UID = 1

-- Nested field access (production-proven from Observo scripts)
function getNestedField(obj, path)
    if obj == nil or path == nil or path == '' then return nil end
    local current = obj
    for key in string.gmatch(path, '[^.]+') do
        if current == nil or current[key] == nil then return nil end
        current = current[key]
    end
    return current
end

function setNestedField(obj, path, value)
    if value == nil or path == nil or path == '' then return end
    local keys = {}
    for key in string.gmatch(path, '[^.]+') do table.insert(keys, key) end
    if #keys == 0 then return end
    local current = obj
    for i = 1, #keys - 1 do
        if current[keys[i]] == nil then current[keys[i]] = {} end
        current = current[keys[i]]
    end
    current[keys[#keys]] = value
end

-- Safe value access with default
function getValue(tbl, key, default)
    local value = tbl[key]
    return value ~= nil and value or default
end

-- Replace userdata nil values (Observo sandbox quirk)
function no_nulls(d, rn)
    if type(d) == "table" then
        for k, v in pairs(d) do
            if type(v) == "userdata" then d[k] = rn
            elseif type(v) == "table" then no_nulls(v, rn) end
        end
    end
    return d
end

-- Flatten nested table to dot-notation keys
function flattenObject(tbl, prefix, result)
    result = result or {}; prefix = prefix or ""
    for k, v in pairs(tbl) do
        local keyPath = prefix ~= "" and (prefix .. "." .. tostring(k)) or tostring(k)
        if type(v) == "table" then flattenObject(v, keyPath, result)
        else result[keyPath] = v end
    end
    return result
end

-- Collect unmapped fields (preserves data not in field mappings)
function copyUnmappedFields(event, mappedPaths, result)
    for k, v in pairs(event) do
        if not mappedPaths[k] and k ~= "_ob" and v ~= nil and v ~= "" then
            setNestedField(result, "unmapped." .. k, v)
        end
    end
end

-- Map GitHub action to OCSF activity_id
local function getActivityId(action)
    if action == nil then return 99 end
    local activityMap = {
        -- GitHub repository actions
        ['create'] = 1,     -- Launch
        ['delete'] = 2,     -- Terminate
        ['push'] = 99,      -- Other
        ['pull'] = 99,      -- Other
        ['merge'] = 99,     -- Other
        ['fork'] = 1,       -- Launch
        ['clone'] = 99,     -- Other
        ['commit'] = 99,    -- Other
        ['release'] = 1,    -- Launch
        ['deploy'] = 1,     -- Launch
        ['build'] = 1,      -- Launch
        ['test'] = 1,       -- Launch
        ['workflow_run'] = 1, -- Launch
        ['workflow_job'] = 1, -- Launch
        -- User/admin actions
        ['login'] = 99,     -- Other
        ['logout'] = 99,    -- Other
        ['invite'] = 99,    -- Other
        ['accept'] = 99,    -- Other
        ['remove'] = 2,     -- Terminate
        ['add'] = 1,        -- Launch
        ['update'] = 99,    -- Other
        ['modify'] = 99,    -- Other
        ['enable'] = 1,     -- Launch
        ['disable'] = 2     -- Terminate
    }
    return activityMap[action] or 99
end

-- Get activity name based on GitHub action
local function getActivityName(action, eventName)
    if eventName then return eventName end
    if action then return "GitHub " .. action end
    return "GitHub Activity"
end

-- Map GitHub severity/level to OCSF severity_id
local function getSeverityId(level, action)
    if level then
        local severityMap = {
            ['critical'] = 5,
            ['high'] = 4,
            ['medium'] = 3,
            ['warning'] = 2,
            ['low'] = 2,
            ['info'] = 1,
            ['informational'] = 1
        }
        return severityMap[string.lower(level)] or 1
    end
    
    -- Default based on action type
    if action then
        local actionSeverity = {
            ['delete'] = 4,
            ['remove'] = 4,
            ['disable'] = 3,
            ['login'] = 1,
            ['logout'] = 1,
            ['create'] = 2,
            ['push'] = 1,
            ['merge'] = 2
        }
        return actionSeverity[action] or 1
    end
    
    return 1 -- Default to Informational
end

-- Parse ISO 8601 timestamp to milliseconds
local function parseTimestamp(timeStr)
    if not timeStr then return os.time() * 1000 end
    
    -- Try ISO 8601 format: 2024-01-15T10:30:45Z or 2024-01-15T10:30:45.123Z
    local year, month, day, hour, min, sec, ms = timeStr:match("(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)%.?(%d*)Z?")
    if year then
        local timestamp = os.time({
            year = tonumber(year),
            month = tonumber(month),
            day = tonumber(day),
            hour = tonumber(hour),
            min = tonumber(min),
            sec = tonumber(sec),
            isdst = false
        })
        local milliseconds = ms and tonumber(ms) or 0
        if #tostring(milliseconds) == 3 then
            return timestamp * 1000 + milliseconds
        else
            return timestamp * 1000
        end
    end
    
    -- Fallback: try Unix timestamp
    local unixTime = tonumber(timeStr)
    if unixTime then
        -- If it's seconds, convert to milliseconds
        if unixTime < 10000000000 then
            return unixTime * 1000
        else
            return unixTime
        end
    end
    
    return os.time() * 1000
end

-- Main transformation function
function processEvent(event)
    if type(event) ~= "table" then return nil end
    
    local result = {}
    local mappedPaths = {}
    
    -- Field mappings for GitHub audit events
    local fieldMappings = {
        -- OCSF required fields
        {type = "computed", target = "class_uid", value = CLASS_UID},
        {type = "computed", target = "category_uid", value = CATEGORY_UID},
        {type = "computed", target = "class_name", value = "Process Activity"},
        {type = "computed", target = "category_name", value = "System Activity"},
        
        -- GitHub event identification
        {type = "direct", source = "action", target = "activity_name"},
        {type = "direct", source = "_document_id", target = "metadata.uid"},
        {type = "direct", source = "event", target = "type_name"},
        
        -- User/Actor information
        {type = "priority", source1 = "actor", source2 = "actor_login", target = "process.user.name"},
        {type = "direct", source = "actor_id", target = "process.user.uid"},
        {type = "direct", source = "actor_location.country_code", target = "process.user.domain"},
        
        -- Process-related fields (GitHub workflow/action context)
        {type = "priority", source1 = "workflow_name", source2 = "job_name", source3 = "action", target = "process.name"},
        {type = "direct", source = "workflow_id", target = "process.pid"},
        {type = "direct", source = "run_id", target = "process.uid"},
        {type = "priority", source1 = "workflow_file", source2 = "config_file", target = "process.file.path"},
        {type = "direct", source = "step_name", target = "process.cmd_line"},
        
        -- Repository/Organization context
        {type = "direct", source = "repo", target = "metadata.product.name"},
        {type = "priority", source1 = "org", source2 = "organization", target = "metadata.product.vendor_name"},
        
        -- Status and outcome
        {type = "direct", source = "conclusion", target = "status"},
        {type = "direct", source = "status", target = "status_detail"},
        {type = "direct", source = "message", target = "message"},
        
        -- Timing
        {type = "priority", source1 = "created_at", source2 = "timestamp", source3 = "@timestamp", target = "start_time"},
        {type = "direct", source = "completed_at", target = "end_time"},
        {type = "direct", source = "duration", target = "duration"},
        
        -- Additional context
        {type = "direct", source = "head_branch", target = "metadata.labels"},
        {type = "direct", source = "head_sha", target = "metadata.correlation_uid"},
        {type = "direct", source = "external_id", target = "metadata.external_uid"}
    }
    
    -- Apply field mappings
    for _, mapping in ipairs(fieldMappings) do
        if mapping.type == "direct" then
            local value = getNestedField(event, mapping.source)
            if value ~= nil and value ~= "" then
                setNestedField(result, mapping.target, value)
                mappedPaths[mapping.source] = true
            end
        elseif mapping.type == "priority" then
            local value = getNestedField(event, mapping.source1)
            mappedPaths[mapping.source1] = true
            
            if value == nil and mapping.source2 then
                value = getNestedField(event, mapping.source2)
                mappedPaths[mapping.source2] = true
            end
            if value == nil and mapping.source3 then
                value = getNestedField(event, mapping.source3)
                mappedPaths[mapping.source3] = true
            end
            
            if value ~= nil and value ~= "" then
                setNestedField(result, mapping.target, value)
            end
        elseif mapping.type == "computed" then
            setNestedField(result, mapping.target, mapping.value)
        end
    end
    
    -- Set activity_id based on GitHub action
    local action = getNestedField(event, "action")
    local activityId = getActivityId(action)
    result.activity_id = activityId
    result.type_uid = CLASS_UID * 100 + activityId
    mappedPaths["action"] = true
    
    -- Set activity_name
    result.activity_name = getActivityName(action, getNestedField(event, "event"))
    mappedPaths["event"] = true
    
    -- Set severity_id
    local level = getNestedField(event, "level") or getNestedField(event, "severity")
    result.severity_id = getSeverityId(level, action)
    if level then mappedPaths["level"] = true end
    mappedPaths["severity"] = true
    
    -- Set time from timestamp
    local timeField = getNestedField(event, "created_at") or 
                     getNestedField(event, "timestamp") or 
                     getNestedField(event, "@timestamp")
    result.time = parseTimestamp(timeField)
    mappedPaths["created_at"] = true
    mappedPaths["timestamp"] = true
    mappedPaths["@timestamp"] = true
    
    -- Set status_id based on status/conclusion
    local status = getNestedField(result, "status") or getNestedField(result, "status_detail")
    if status then
        local statusMap = {
            ['success'] = 1,
            ['completed'] = 1,
            ['failure'] = 2,
            ['error'] = 2,
            ['cancelled'] = 3,
            ['skipped'] = 99,
            ['pending'] = 99,
            ['queued'] = 99,
            ['in_progress'] = 99,
            ['running'] = 99
        }
        result.status_id = statusMap[string.lower(status)] or 99
    else
        result.status_id = 99 -- Unknown
    end
    
    -- Set metadata version
    result.metadata = result.metadata or {}
    result.metadata.version = "1.0.0"
    
    -- Handle raw_data - preserve original event
    if event._raw or event.raw_data then
        result.raw_data = event._raw or event.raw_data
        mappedPaths["_raw"] = true
        mappedPaths["raw_data"] = true
    end
    
    -- Set count (default to 1 for single event)
    if not result.count then
        result.count = 1
    end
    
    -- Collect unmapped fields
    copyUnmappedFields(event, mappedPaths, result)
    
    -- Clean up nil values and empty tables
    result = no_nulls(result, nil)
    
    return result
end