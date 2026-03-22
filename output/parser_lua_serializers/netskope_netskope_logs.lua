-- Netskope Network Activity OCSF Transformation
-- Maps Netskope logs to OCSF Network Activity class (4001)

-- OCSF constants
local CLASS_UID = 4001
local CATEGORY_UID = 4

-- Activity ID mapping based on Netskope action/activity
local ACTIVITY_MAPPING = {
    allow = 1,
    block = 2,
    alert = 6,
    monitor = 99,
    quarantine = 5,
    scan = 99,
    bypass = 1,
    coach = 99
}

-- Severity mapping from Netskope to OCSF
local function getSeverityId(alert_type, action)
    if alert_type then
        local severityMap = {
            critical = 5,
            high = 4,
            medium = 3,
            low = 2,
            info = 1,
            informational = 1
        }
        return severityMap[string.lower(alert_type)] or 0
    end
    
    -- Fallback to action-based severity
    if action then
        local actionMap = {
            block = 4,
            alert = 3,
            quarantine = 4,
            allow = 1,
            monitor = 1
        }
        return actionMap[string.lower(action)] or 0
    end
    
    return 0 -- Unknown
end

-- Get activity ID from action/activity
local function getActivityId(action, activity)
    local key = action or activity
    if key then
        return ACTIVITY_MAPPING[string.lower(key)] or 99
    end
    return 99 -- Other
end

-- Convert timestamp to milliseconds since epoch
local function parseTimestamp(timestamp)
    if not timestamp or timestamp == "" then
        return os.time() * 1000
    end
    
    -- Try parsing various timestamp formats
    local patterns = {
        "(%d+)-(%d+)-(%d+) (%d+):(%d+):(%d+)",  -- YYYY-MM-DD HH:MM:SS
        "(%d+)/(%d+)/(%d+) (%d+):(%d+):(%d+)",  -- MM/DD/YYYY HH:MM:SS
        "(%d+)%-(%d+)%-(%d+)T(%d+):(%d+):(%d+)", -- ISO format
    }
    
    for _, pattern in ipairs(patterns) do
        local yr, mo, dy, hr, mn, sc = timestamp:match(pattern)
        if yr then
            local time_table = {
                year = tonumber(yr),
                month = tonumber(mo),
                day = tonumber(dy),
                hour = tonumber(hr),
                min = tonumber(mn),
                sec = tonumber(sc),
                isdst = false
            }
            return os.time(time_table) * 1000
        end
    end
    
    -- If it's already a unix timestamp
    local unix_ts = tonumber(timestamp)
    if unix_ts then
        -- Convert to milliseconds if it looks like seconds
        if unix_ts < 2000000000 then
            return unix_ts * 1000
        end
        return unix_ts
    end
    
    return os.time() * 1000
end

-- Helper functions from production Observo scripts
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

function getValue(tbl, key, default)
    local value = tbl[key]
    return value ~= nil and value or default
end

function copyUnmappedFields(event, mappedPaths, result)
    for k, v in pairs(event) do
        if not mappedPaths[k] and k ~= "_ob" and v ~= nil and v ~= "" and type(v) ~= "userdata" then
            setNestedField(result, "unmapped." .. k, v)
        end
    end
end

-- Field mappings for Netskope to OCSF transformation
local fieldMappings = {
    -- Core OCSF fields
    {type = "computed", target = "class_uid", value = CLASS_UID},
    {type = "computed", target = "category_uid", value = CATEGORY_UID},
    {type = "computed", target = "class_name", value = "Network Activity"},
    {type = "computed", target = "category_name", value = "Network Activity"},
    
    -- Direct field mappings
    {type = "direct", source = "count", target = "count"},
    {type = "direct", source = "connection_id", target = "connection_info.uid"},
    {type = "direct", source = "app", target = "app_name"},
    {type = "direct", source = "appcategory", target = "category_name"},
    {type = "direct", source = "browser", target = "http_request.user_agent"},
    {type = "direct", source = "device", target = "device.name"},
    {type = "direct", source = "device_classification", target = "device.type"},
    
    -- Metadata fields
    {type = "computed", target = "metadata.product.name", value = "Netskope"},
    {type = "computed", target = "metadata.product.vendor_name", value = "Netskope"},
    {type = "direct", source = "_nshostname", target = "metadata.product.hostname"},
    
    -- Alert/DLP fields
    {type = "direct", source = "alert_name", target = "finding.title"},
    {type = "direct", source = "dlp_incident_id", target = "finding.uid"},
    {type = "direct", source = "dlp_file", target = "file.name"},
    
    -- Session and access info
    {type = "direct", source = "app_session_id", target = "session.uid"},
    {type = "direct", source = "browser_session_id", target = "http_request.uid"},
    {type = "direct", source = "access_method", target = "connection_info.direction"},
}

function processEvent(event)
    if type(event) ~= "table" then
        return nil
    end
    
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
        elseif mapping.type == "computed" then
            setNestedField(result, mapping.target, mapping.value)
        end
    end
    
    -- Set activity_id and type_uid based on action/activity
    local activity_id = getActivityId(event.action, event.activity)
    result.activity_id = activity_id
    result.type_uid = CLASS_UID * 100 + activity_id
    mappedPaths["action"] = true
    mappedPaths["activity"] = true
    
    -- Set activity_name
    if event.activity then
        result.activity_name = event.activity
    elseif event.action then
        result.activity_name = event.action
    else
        result.activity_name = "Network Activity"
    end
    
    -- Set severity_id
    result.severity_id = getSeverityId(event.alert_type, event.action)
    mappedPaths["alert_type"] = true
    
    -- Set timestamp
    local timestamp = event.timestamp or event._insertion_epoch_timestamp or event._src_epoch_now
    result.time = parseTimestamp(timestamp)
    mappedPaths["timestamp"] = true
    mappedPaths["_insertion_epoch_timestamp"] = true
    mappedPaths["_src_epoch_now"] = true
    
    -- Set status based on action
    if event.action then
        if event.action == "allow" then
            result.status = "Success"
            result.status_id = 1
        elseif event.action == "block" then
            result.status = "Failure" 
            result.status_id = 2
        else
            result.status = event.action
            result.status_id = 99
        end
    end
    
    -- Set message from alert or category
    if event.alert then
        result.message = event.alert
        mappedPaths["alert"] = true
    elseif event.category then
        result.message = event.category
        mappedPaths["category"] = true
    end
    
    -- Create observables array
    local observables = {}
    if event.srcip then
        table.insert(observables, {
            type_id = 2,
            type = "IP Address", 
            name = "src_endpoint.ip",
            value = event.srcip
        })
        result.src_endpoint = result.src_endpoint or {}
        result.src_endpoint.ip = event.srcip
        mappedPaths["srcip"] = true
    end
    
    if event.dstip then
        table.insert(observables, {
            type_id = 2,
            type = "IP Address",
            name = "dst_endpoint.ip", 
            value = event.dstip
        })
        result.dst_endpoint = result.dst_endpoint or {}
        result.dst_endpoint.ip = event.dstip
        mappedPaths["dstip"] = true
    end
    
    if #observables > 0 then
        result.observables = observables
    end
    
    -- Copy unmapped fields to preserve data
    copyUnmappedFields(event, mappedPaths, result)
    
    return result
end