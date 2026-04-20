-- Netskope Network Activity OCSF Transformation
-- Maps Netskope logs to OCSF Network Activity class (4001)

-- Constants
local CLASS_UID = 4001
local CATEGORY_UID = 4
local CLASS_NAME = "Network Activity"
local CATEGORY_NAME = "Network Activity"

-- Helper Functions
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
        if not mappedPaths[k] and k ~= "_ob" and v ~= nil and v ~= "" then
            setNestedField(result, "unmapped." .. k, v)
        end
    end
end

-- Get severity ID based on alert type or action
local function getSeverityId(event)
    local alert_type = event.alert_type
    local action = event.action
    local alert = event.alert
    
    if alert_type then
        local severityMap = {
            ["Critical"] = 5,
            ["High"] = 4, 
            ["Medium"] = 3,
            ["Low"] = 2,
            ["Info"] = 1,
            ["Informational"] = 1
        }
        return severityMap[alert_type] or 0
    end
    
    if action then
        if action:lower():match("block") or action:lower():match("deny") or action:lower():match("drop") then
            return 4 -- High
        elseif action:lower():match("allow") or action:lower():match("permit") then
            return 1 -- Informational
        elseif action:lower():match("alert") or action:lower():match("warn") then
            return 3 -- Medium
        end
    end
    
    if alert and alert ~= "no" and alert ~= "false" then
        return 3 -- Medium for alerts
    end
    
    return 0 -- Unknown
end

-- Get activity ID based on Netskope activity
local function getActivityId(event)
    local activity = event.activity
    local action = event.action
    
    if activity then
        local activityMap = {
            ["Login"] = 1,
            ["Logout"] = 2, 
            ["Upload"] = 3,
            ["Download"] = 4,
            ["Delete"] = 5,
            ["Create"] = 6,
            ["Update"] = 7,
            ["Share"] = 8,
            ["Access"] = 9,
            ["Block"] = 10
        }
        return activityMap[activity] or 99
    end
    
    if action then
        if action:lower():match("block") or action:lower():match("deny") then
            return 10 -- Block
        elseif action:lower():match("allow") or action:lower():match("permit") then
            return 9 -- Access
        end
    end
    
    return 99 -- Other
end

-- Convert timestamp to milliseconds
local function parseTimestamp(timestamp)
    if not timestamp then return nil end
    
    -- Try parsing epoch timestamp (already in seconds)
    local epochTime = tonumber(timestamp)
    if epochTime then
        return epochTime * 1000
    end
    
    -- Try parsing ISO format timestamp
    local yr, mo, dy, hr, mn, sc = timestamp:match("(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)")
    if yr then
        return os.time({
            year = tonumber(yr),
            month = tonumber(mo),
            day = tonumber(dy),
            hour = tonumber(hr),
            min = tonumber(mn),
            sec = tonumber(sc),
            isdst = false
        }) * 1000
    end
    
    return nil
end

-- Main transformation function
function processEvent(event)
    if type(event) ~= "table" then return nil end
    
    local result = {}
    local mappedPaths = {}
    
    -- Field mappings using table-driven approach
    local fieldMappings = {
        -- Core OCSF fields
        {type = "computed", target = "class_uid", value = CLASS_UID},
        {type = "computed", target = "category_uid", value = CATEGORY_UID},
        {type = "computed", target = "class_name", value = CLASS_NAME},
        {type = "computed", target = "category_name", value = CATEGORY_NAME},
        
        -- Network endpoints
        {type = "direct", source = "srcip", target = "src_endpoint.ip"},
        {type = "direct", source = "src_ip", target = "src_endpoint.ip"},
        {type = "direct", source = "srcport", target = "src_endpoint.port"},
        {type = "direct", source = "src_port", target = "src_endpoint.port"},
        {type = "direct", source = "src_host", target = "src_endpoint.hostname"},
        {type = "direct", source = "dstip", target = "dst_endpoint.ip"},
        {type = "direct", source = "dst_ip", target = "dst_endpoint.ip"},
        {type = "direct", source = "dstport", target = "dst_endpoint.port"},
        {type = "direct", source = "dst_port", target = "dst_endpoint.port"},
        {type = "direct", source = "dst_host", target = "dst_endpoint.hostname"},
        
        -- Protocol and connection details
        {type = "direct", source = "protocol", target = "protocol_name"},
        {type = "direct", source = "connection_id", target = "connection_info.uid"},
        
        -- Status and action
        {type = "direct", source = "action", target = "disposition"},
        {type = "direct", source = "status", target = "status"},
        {type = "direct", source = "count", target = "count"},
        
        -- Application and category
        {type = "direct", source = "app", target = "app_name"},
        {type = "direct", source = "appcategory", target = "category_name"},
        {type = "direct", source = "category", target = "category_name"},
        
        -- Device and user info
        {type = "direct", source = "device", target = "device.name"},
        {type = "direct", source = "device_classification", target = "device.type"},
        {type = "direct", source = "user", target = "actor.user.name"},
        {type = "direct", source = "username", target = "actor.user.name"},
        
        -- Browser information
        {type = "direct", source = "browser", target = "http_request.user_agent"},
        {type = "direct", source = "browser_version", target = "metadata.product.version"},
        
        -- Alert information
        {type = "direct", source = "alert_name", target = "finding.title"},
        {type = "direct", source = "alert_type", target = "finding.types"},
        {type = "direct", source = "dlp_incident_id", target = "finding.uid"},
        
        -- Session identifiers
        {type = "direct", source = "app_session_id", target = "session.uid"},
        {type = "direct", source = "browser_session_id", target = "session.uid"},
        
        -- Metadata
        {type = "computed", target = "metadata.product.name", value = "Netskope Security Cloud"},
        {type = "computed", target = "metadata.product.vendor_name", value = "Netskope"},
    }
    
    -- Apply field mappings
    for _, mapping in ipairs(fieldMappings) do
        if mapping.type == "direct" then
            local value = getNestedField(event, mapping.source)
            if value ~= nil and value ~= "" then
                setNestedField(result, mapping.target, value)
                mappedPaths[mapping.source] = true
            end
        elseif mapping.type == "computed" then
            setNestedField(result, mapping.target, mapping.value)
        end
    end
    
    -- Set activity_id and type_uid
    local activity_id = getActivityId(event)
    result.activity_id = activity_id
    result.type_uid = CLASS_UID * 100 + activity_id
    
    -- Set severity
    result.severity_id = getSeverityId(event)
    
    -- Set activity name
    local activity_name = event.activity or event.action or "Network Activity"
    result.activity_name = activity_name
    
    -- Handle timestamp
    local timestamp = event.timestamp or event._insertion_epoch_timestamp or event._src_epoch_now
    local eventTime = parseTimestamp(timestamp)
    result.time = eventTime or (os.time() * 1000)
    
    -- Set message from various sources
    local message = event.message or event.alert_name
    if not message and event.activity and event.app then
        message = event.activity .. " on " .. event.app
    end
    if message then
        result.message = message
    end
    
    -- Mark mapped paths for common Netskope fields
    local commonFields = {
        "timestamp", "_insertion_epoch_timestamp", "_src_epoch_now",
        "activity", "action", "app", "user", "username", "srcip", "src_ip", 
        "dstip", "dst_ip", "protocol", "alert_name", "alert_type", "message"
    }
    for _, field in ipairs(commonFields) do
        mappedPaths[field] = true
    end
    
    -- Copy unmapped fields to preserve data
    copyUnmappedFields(event, mappedPaths, result)
    
    return result
end