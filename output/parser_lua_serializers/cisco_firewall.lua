-- Cisco Firewall to OCSF Network Activity transformation
-- OCSF Class: Network Activity (4001), Category: Network Activity (4)

-- Constants
local CLASS_UID = 4001
local CATEGORY_UID = 4
local DEFAULT_ACTIVITY_ID = 99

-- Helper functions for nested field access
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

-- Clean empty tables recursively
function cleanEmptyTables(tbl)
    if type(tbl) ~= "table" then return tbl end
    local hasContent = false
    for k, v in pairs(tbl) do
        if type(v) == "table" then
            local cleaned = cleanEmptyTables(v)
            if cleaned == nil then
                tbl[k] = nil
            else
                tbl[k] = cleaned
                hasContent = true
            end
        elseif v ~= nil and v ~= "" then
            hasContent = true
        end
    end
    return hasContent and tbl or nil
end

-- Severity mapping for Cisco firewall logs
local function getSeverityId(level)
    if level == nil then return 0 end
    local levelStr = tostring(level):lower()
    local severityMap = {
        emergency = 5,      -- Critical
        alert = 5,          -- Critical
        critical = 5,       -- Critical
        error = 4,          -- High
        warning = 3,        -- Medium
        notice = 2,         -- Low
        informational = 1,  -- Informational
        debug = 1,          -- Informational
        ["0"] = 5, ["1"] = 5, ["2"] = 5, ["3"] = 4,  -- Numeric levels
        ["4"] = 3, ["5"] = 2, ["6"] = 1, ["7"] = 1
    }
    return severityMap[levelStr] or 0
end

-- Activity ID mapping based on Cisco firewall actions
local function getActivityId(action)
    if action == nil then return DEFAULT_ACTIVITY_ID end
    local actionStr = tostring(action):lower()
    local activityMap = {
        allow = 1,          -- Allow
        permit = 1,         -- Allow
        accept = 1,         -- Allow
        deny = 2,           -- Deny
        block = 2,          -- Deny
        drop = 2,           -- Deny
        reject = 2,         -- Deny
        teardown = 3,       -- Close
        built = 4,          -- Open
        connect = 4,        -- Open
    }
    return activityMap[actionStr] or DEFAULT_ACTIVITY_ID
end

-- Get activity name from action
local function getActivityName(action)
    if action == nil then return "Other" end
    local actionStr = tostring(action):lower()
    local nameMap = {
        allow = "Allow",
        permit = "Allow", 
        accept = "Allow",
        deny = "Deny",
        block = "Deny",
        drop = "Deny",
        reject = "Deny",
        teardown = "Close",
        built = "Open",
        connect = "Open"
    }
    return nameMap[actionStr] or "Other"
end

-- Parse timestamp to milliseconds
local function parseTimestamp(timeStr)
    if timeStr == nil or timeStr == "" then return os.time() * 1000 end
    
    -- Try various timestamp formats common in Cisco logs
    -- ISO format: 2023-01-01T12:00:00Z
    local yr, mo, dy, hr, mn, sc = timeStr:match("(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)")
    if yr then
        return os.time({year=tonumber(yr), month=tonumber(mo), day=tonumber(dy),
                       hour=tonumber(hr), min=tonumber(mn), sec=tonumber(sc), isdst=false}) * 1000
    end
    
    -- Syslog format: Jan 01 12:00:00
    local months = {Jan=1, Feb=2, Mar=3, Apr=4, May=5, Jun=6,
                   Jul=7, Aug=8, Sep=9, Oct=10, Nov=11, Dec=12}
    local mon, day, hour, min, sec = timeStr:match("(%a+)%s+(%d+)%s+(%d+):(%d+):(%d+)")
    if mon and months[mon] then
        local currentYear = os.date("*t").year
        return os.time({year=currentYear, month=months[mon], day=tonumber(day),
                       hour=tonumber(hour), min=tonumber(min), sec=tonumber(sec), isdst=false}) * 1000
    end
    
    -- Unix timestamp
    local timestamp = tonumber(timeStr)
    if timestamp then
        return timestamp < 10000000000 and timestamp * 1000 or timestamp
    end
    
    return os.time() * 1000
end

-- Field mappings for Cisco firewall logs
local fieldMappings = {
    -- Core OCSF fields
    {type = "computed", target = "class_uid", value = CLASS_UID},
    {type = "computed", target = "category_uid", value = CATEGORY_UID},
    {type = "computed", target = "class_name", value = "Network Activity"},
    {type = "computed", target = "category_name", value = "Network Activity"},
    
    -- Message and raw data
    {type = "direct", source = "message", target = "message"},
    {type = "direct", source = "raw", target = "raw_data"},
    {type = "direct", source = "raw_data", target = "raw_data"},
    {type = "direct", source = "original_message", target = "raw_data"},
    
    -- Network endpoints - source
    {type = "priority", source1 = "src_ip", source2 = "source_ip", target = "src_endpoint.ip"},
    {type = "priority", source1 = "src_port", source2 = "source_port", target = "src_endpoint.port"},
    {type = "priority", source1 = "src_host", source2 = "source_host", target = "src_endpoint.hostname"},
    
    -- Network endpoints - destination  
    {type = "priority", source1 = "dst_ip", source2 = "dest_ip", target = "dst_endpoint.ip"},
    {type = "priority", source1 = "dst_port", source2 = "dest_port", target = "dst_endpoint.port"},
    {type = "priority", source1 = "dst_host", source2 = "dest_host", target = "dst_endpoint.hostname"},
    
    -- Protocol
    {type = "priority", source1 = "protocol", source2 = "proto", target = "protocol_name"},
    
    -- Status and action
    {type = "direct", source = "action", target = "status"},
    {type = "direct", source = "status", target = "status_detail"},
    
    -- Connection metrics
    {type = "direct", source = "bytes", target = "traffic.bytes"},
    {type = "direct", source = "packets", target = "traffic.packets"},
    {type = "direct", source = "duration", target = "duration"},
    {type = "direct", source = "count", target = "count"},
    
    -- Metadata
    {type = "computed", target = "metadata.product.name", value = "Cisco Firewall"},
    {type = "computed", target = "metadata.product.vendor_name", value = "Cisco"},
    {type = "computed", target = "metadata.version", value = "1.0.0"},
    
    -- Device info
    {type = "direct", source = "device", target = "device.name"},
    {type = "direct", source = "hostname", target = "device.hostname"},
    {type = "direct", source = "facility", target = "metadata.log_name"},
}

function processEvent(event)
    -- Validate input
    if type(event) ~= "table" then return nil end
    
    local result = {}
    local mappedPaths = {}
    
    -- Process field mappings
    for _, mapping in ipairs(fieldMappings) do
        if mapping.type == "direct" then
            local value = getNestedField(event, mapping.source)
            if value ~= nil and value ~= "" then
                setNestedField(result, mapping.target, value)
            end
            mappedPaths[mapping.source] = true
            
        elseif mapping.type == "priority" then
            local value = getNestedField(event, mapping.source1)
            if value == nil and mapping.source2 then
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
    
    -- Set activity ID and type based on action
    local action = event.action or event.status
    local activityId = getActivityId(action)
    result.activity_id = activityId
    result.type_uid = CLASS_UID * 100 + activityId
    result.activity_name = getActivityName(action)
    
    -- Set severity
    local severity = event.severity or event.priority or event.level
    result.severity_id = getSeverityId(severity)
    
    -- Parse timestamp
    local timestamp = event.timestamp or event.time or event.date
    result.time = parseTimestamp(timestamp)
    
    -- Set status_id based on action
    if action then
        local actionStr = tostring(action):lower()
        if actionStr:match("allow") or actionStr:match("permit") or actionStr:match("accept") then
            result.status_id = 1  -- Success
        elseif actionStr:match("deny") or actionStr:match("block") or actionStr:match("drop") then
            result.status_id = 2  -- Failure
        else
            result.status_id = 99 -- Other
        end
    else
        result.status_id = 0  -- Unknown
    end
    
    -- Convert port numbers to integers
    if result.src_endpoint and result.src_endpoint.port then
        result.src_endpoint.port = tonumber(result.src_endpoint.port)
    end
    if result.dst_endpoint and result.dst_endpoint.port then
        result.dst_endpoint.port = tonumber(result.dst_endpoint.port)
    end
    
    -- Add observables for key network indicators
    local observables = {}
    if result.src_endpoint and result.src_endpoint.ip then
        table.insert(observables, {
            type_id = 2,
            type = "IP Address", 
            name = "src_endpoint.ip",
            value = result.src_endpoint.ip
        })
    end
    if result.dst_endpoint and result.dst_endpoint.ip then
        table.insert(observables, {
            type_id = 2,
            type = "IP Address",
            name = "dst_endpoint.ip", 
            value = result.dst_endpoint.ip
        })
    end
    if #observables > 0 then
        result.observables = observables
    end
    
    -- Copy unmapped fields to preserve original data
    copyUnmappedFields(event, mappedPaths, result)
    
    -- Clean empty tables
    result = cleanEmptyTables(result)
    
    return result
end