-- Cisco Duo Authentication Event Parser for OCSF
-- Maps Cisco Duo authentication events to OCSF Authentication class (3002)

local CLASS_UID = 3002
local CATEGORY_UID = 3
local CLASS_NAME = "Authentication"
local CATEGORY_NAME = "Identity & Access Management"

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

-- Collect unmapped fields (preserves data not in field mappings)
function copyUnmappedFields(event, mappedPaths, result)
    for k, v in pairs(event) do
        if not mappedPaths[k] and k ~= "_ob" and v ~= nil and v ~= "" then
            setNestedField(result, "unmapped." .. k, v)
        end
    end
end

-- Parse ISO timestamp to milliseconds
local function parseTimestamp(timestamp)
    if not timestamp then return nil end
    local yr, mo, dy, hr, mn, sc = timestamp:match("(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)")
    if yr then
        return os.time({year=tonumber(yr), month=tonumber(mo), day=tonumber(dy),
                       hour=tonumber(hr), min=tonumber(mn), sec=tonumber(sc), isdst=false}) * 1000
    end
    return nil
end

-- Map Duo result to OCSF status and severity
local function mapResultToStatus(result)
    if not result then return 0, 0 end -- Unknown status and severity
    
    local statusMap = {
        SUCCESS = {status_id = 1, severity_id = 1}, -- Success, Informational
        FAILURE = {status_id = 2, severity_id = 3}, -- Failure, Medium
        DENIED = {status_id = 2, severity_id = 3},  -- Failure, Medium
        FRAUD = {status_id = 2, severity_id = 4},   -- Failure, High
        ERROR = {status_id = 2, severity_id = 3}    -- Failure, Medium
    }
    
    local mapping = statusMap[string.upper(result)] or {status_id = 0, severity_id = 0}
    return mapping.status_id, mapping.severity_id
end

-- Map Duo event type to OCSF activity
local function mapEventTypeToActivity(eventType, result)
    if not eventType then
        -- Fallback based on result
        if result and string.upper(result) == "SUCCESS" then
            return 1, "Logon" -- Successful authentication
        else
            return 2, "Logoff" -- Failed authentication
        end
    end
    
    local activityMap = {
        authentication = 1, -- Logon
        enrollment = 3,     -- Authentication
        bypass = 1,         -- Logon
        fraud = 2          -- Logoff (treated as failed auth)
    }
    
    local activityId = activityMap[string.lower(eventType)] or 99
    local activityName = activityId == 1 and "Logon" or 
                        activityId == 2 and "Logoff" or 
                        activityId == 3 and "Authentication" or "Other"
    
    return activityId, activityName
end

-- Field mappings for Cisco Duo to OCSF
local fieldMappings = {
    -- Direct mappings
    {type = "direct", source = "message", target = "message"},
    {type = "direct", source = "txid", target = "metadata.uid"},
    {type = "direct", source = "reason", target = "status_detail"},
    {type = "direct", source = "access_device.hostname", target = "src_endpoint.hostname"},
    {type = "direct", source = "access_device.ip", target = "src_endpoint.ip"},
    {type = "direct", source = "auth_device.ip", target = "dst_endpoint.ip"},
    {type = "direct", source = "auth_device.name", target = "dst_endpoint.hostname"},
    {type = "direct", source = "application.name", target = "metadata.product.name"},
    
    -- User mappings - priority order
    {type = "priority", source1 = "user.name", source2 = "username", target = "actor.user.name"},
    {type = "direct", source = "user.key", target = "actor.user.uid"},
    {type = "direct", source = "email", target = "actor.user.email_addr"},
    
    -- Location mappings
    {type = "direct", source = "access_device.location.city", target = "src_endpoint.location.city"},
    {type = "direct", source = "access_device.location.country", target = "src_endpoint.location.country"},
    {type = "direct", source = "auth_device.location.city", target = "dst_endpoint.location.city"},
    {type = "direct", source = "auth_device.location.country", target = "dst_endpoint.location.country"},
    
    -- Computed values
    {type = "computed", target = "class_uid", value = CLASS_UID},
    {type = "computed", target = "category_uid", value = CATEGORY_UID},
    {type = "computed", target = "class_name", value = CLASS_NAME},
    {type = "computed", target = "category_name", value = CATEGORY_NAME},
    {type = "computed", target = "metadata.product.vendor_name", value = "Cisco"},
}

function processEvent(event)
    if type(event) ~= "table" then return nil end

    local result = {}
    local mappedPaths = {}

    -- Apply field mappings
    for _, mapping in ipairs(fieldMappings) do
        if mapping.type == "direct" then
            local value = getNestedField(event, mapping.source)
            if value ~= nil and value ~= "" then 
                setNestedField(result, mapping.target, value) 
            end
            mappedPaths[mapping.source] = true
        elseif mapping.type == "priority" then
            local value = getNestedField(event, mapping.source1)
            if value == nil or value == "" then 
                value = getNestedField(event, mapping.source2) 
            end
            if value ~= nil and value ~= "" then 
                setNestedField(result, mapping.target, value) 
            end
            mappedPaths[mapping.source1] = true
            if mapping.source2 then mappedPaths[mapping.source2] = true end
        elseif mapping.type == "computed" then
            setNestedField(result, mapping.target, mapping.value)
        end
    end

    -- Mark additional mapped paths
    local additionalMappedPaths = {
        "result", "event.type", "isotimestamp", "timestamp", "user.groups",
        "host", "object", "site.id", "dataSource.category", "dataSource.name",
        "dataSource.vendor", "application.key", "auth_device.key",
        "category_name", "category_uid", "class_uid", "activity_name",
        "activity_id", "type_uid", "OCSF_version", "observables",
        "class_name", "type_name", "user.type_id"
    }
    for _, path in ipairs(additionalMappedPaths) do
        mappedPaths[path] = true
    end

    -- Handle timestamp - priority order
    local eventTime = getNestedField(event, 'isotimestamp') or getNestedField(event, 'timestamp')
    local parsedTime = parseTimestamp(eventTime)
    result.time = parsedTime or (os.time() * 1000)

    -- Map result to status and severity
    local duoResult = getNestedField(event, 'result')
    local statusId, severityId = mapResultToStatus(duoResult)
    result.status_id = statusId
    result.severity_id = severityId
    if duoResult then
        result.status = duoResult
    end

    -- Map event type to activity
    local eventType = getNestedField(event, 'event.type')
    local activityId, activityName = mapEventTypeToActivity(eventType, duoResult)
    result.activity_id = activityId
    result.activity_name = activityName
    result.type_uid = CLASS_UID * 100 + activityId

    -- Build observables array
    local observables = {}
    local srcIp = getNestedField(result, 'src_endpoint.ip')
    if srcIp then
        table.insert(observables, {
            type_id = 2,
            type = "IP Address",
            name = "src_endpoint.ip",
            value = srcIp
        })
    end
    
    local userName = getNestedField(result, 'actor.user.name')
    if userName then
        table.insert(observables, {
            type_id = 4,
            type = "User Name", 
            name = "actor.user.name",
            value = userName
        })
    end
    
    if #observables > 0 then
        result.observables = observables
    end

    -- Set raw_data if available
    if event.message then
        result.raw_data = event.message
    end

    -- Handle user groups if present
    local userGroups = getNestedField(event, 'user.groups')
    if userGroups then
        if type(userGroups) == "table" then
            setNestedField(result, 'actor.user.groups', userGroups)
        else
            setNestedField(result, 'actor.user.groups', {userGroups})
        end
    end

    -- Copy unmapped fields
    copyUnmappedFields(event, mappedPaths, result)

    return result
end