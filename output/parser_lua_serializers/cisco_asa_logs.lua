-- Cisco ASA Network Activity OCSF Transformation
-- Class: Network Activity (4001), Category: Network Activity (4)

local CLASS_UID = 4001
local CATEGORY_UID = 4

-- Nested field access helper
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

-- Collect unmapped fields
function copyUnmappedFields(event, mappedPaths, result)
    for k, v in pairs(event) do
        if not mappedPaths[k] and k ~= "_ob" and v ~= nil and v ~= "" then
            setNestedField(result, "unmapped." .. k, v)
        end
    end
end

-- Convert ISO timestamp to milliseconds since epoch
function parseTimestamp(timeStr)
    if not timeStr or type(timeStr) ~= "string" then return nil end
    -- Match ISO format: YYYY-MM-DDTHH:MM:SS[.sss][Z|±HH:MM]
    local yr, mo, dy, hr, mn, sc = timeStr:match("(%d%d%d%d)-(%d%d)-(%d%d)T(%d%d):(%d%d):(%d%d)")
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

-- Map result strings to severity
function getSeverityId(result)
    if not result then return 0 end
    local resultLower = string.lower(tostring(result))
    if resultLower:find("success") or resultLower:find("allow") then return 1 end
    if resultLower:find("deny") or resultLower:find("block") or resultLower:find("fail") then return 3 end
    if resultLower:find("error") then return 4 end
    return 0
end

-- Map activity based on event type or category
function getActivityInfo(event)
    local eventType = getNestedField(event, 'event.type')
    local categoryName = event.category_name
    local activityName = event.activity_name
    
    -- If activity_id is already provided, use it
    local activityId = event.activity_id
    if activityId and type(activityId) == "number" then
        return activityId, activityName or "Network Activity"
    end
    
    -- Determine activity based on event type or category
    if eventType then
        local eventTypeLower = string.lower(tostring(eventType))
        if eventTypeLower:find("connect") then 
            return 1, "Connect"
        elseif eventTypeLower:find("disconnect") then 
            return 2, "Disconnect"
        elseif eventTypeLower:find("deny") or eventTypeLower:find("block") then 
            return 3, "Deny"
        elseif eventTypeLower:find("allow") or eventTypeLower:find("permit") then 
            return 4, "Allow"
        end
    end
    
    if categoryName then
        local catLower = string.lower(tostring(categoryName))
        if catLower:find("firewall") then 
            return 3, "Firewall Activity"
        elseif catLower:find("vpn") then 
            return 1, "VPN Activity"
        end
    end
    
    return 99, activityName or "Network Activity"
end

-- Field mappings configuration
local fieldMappings = {
    {type = "direct", source = "message", target = "message"},
    {type = "direct", source = "txid", target = "metadata.correlation_uid"},
    {type = "direct", source = "reason", target = "status_detail"},
    {type = "direct", source = "result", target = "status"},
    {type = "direct", source = "host", target = "src_endpoint.hostname"},
    {type = "direct", source = "username", target = "actor.user.name"},
    {type = "direct", source = "email", target = "actor.user.email_addr"},
    {type = "computed", target = "class_uid", value = CLASS_UID},
    {type = "computed", target = "category_uid", value = CATEGORY_UID},
    {type = "computed", target = "class_name", value = "Network Activity"},
    {type = "computed", target = "category_name", value = "Network Activity"},
    
    -- Device mappings
    {type = "direct", source = "access_device.hostname", target = "src_endpoint.hostname"},
    {type = "direct", source = "access_device.ip", target = "src_endpoint.ip"},
    {type = "direct", source = "auth_device.ip", target = "dst_endpoint.ip"},
    {type = "direct", source = "auth_device.name", target = "dst_endpoint.hostname"},
    
    -- User mappings with priority
    {type = "priority", source1 = "user.name", source2 = "username", target = "actor.user.name"},
    {type = "direct", source = "user.key", target = "actor.user.uid"},
    {type = "direct", source = "user.groups", target = "actor.user.groups"},
    {type = "direct", source = "user.type_id", target = "actor.user.type_id"},
    
    -- Application mappings
    {type = "direct", source = "application.name", target = "app_name"},
    {type = "direct", source = "application.key", target = "metadata.product.uid"},
    
    -- Metadata mappings
    {type = "direct", source = "dataSource.name", target = "metadata.product.name"},
    {type = "direct", source = "dataSource.vendor", target = "metadata.product.vendor_name"},
    {type = "direct", source = "OCSF_version", target = "metadata.version"},
    {type = "direct", source = "site.id", target = "metadata.tenant_uid"}
}

function processEvent(event)
    if type(event) ~= "table" then return nil end

    local result = {}
    local mappedPaths = {}

    -- Apply field mappings
    for _, mapping in ipairs(fieldMappings) do
        if mapping.type == "direct" then
            local value = getNestedField(event, mapping.source)
            if value ~= nil then 
                setNestedField(result, mapping.target, value)
            end
            mappedPaths[mapping.source] = true
        elseif mapping.type == "priority" then
            local value = getNestedField(event, mapping.source1)
            if value == nil and mapping.source2 then 
                value = getNestedField(event, mapping.source2)
            end
            if value ~= nil then 
                setNestedField(result, mapping.target, value)
            end
            mappedPaths[mapping.source1] = true
            if mapping.source2 then 
                mappedPaths[mapping.source2] = true 
            end
        elseif mapping.type == "computed" then
            setNestedField(result, mapping.target, mapping.value)
        end
    end

    -- Set activity information
    local activityId, activityName = getActivityInfo(event)
    result.activity_id = activityId
    result.activity_name = activityName
    result.type_uid = CLASS_UID * 100 + activityId
    mappedPaths["activity_id"] = true
    mappedPaths["activity_name"] = true
    mappedPaths["event.type"] = true
    mappedPaths["category_name"] = true

    -- Set severity based on result
    result.severity_id = getSeverityId(event.result)

    -- Handle timestamp conversion
    local eventTime = event.isotimestamp or event.timestamp
    if eventTime then
        local timeMs = parseTimestamp(eventTime)
        if timeMs then
            result.time = timeMs
        else
            result.time = os.time() * 1000
        end
    else
        result.time = os.time() * 1000
    end
    mappedPaths["isotimestamp"] = true
    mappedPaths["timestamp"] = true

    -- Set status_id based on status/result
    if result.status then
        local statusLower = string.lower(tostring(result.status))
        if statusLower:find("success") or statusLower:find("allow") then
            result.status_id = 1  -- Success
        elseif statusLower:find("fail") or statusLower:find("deny") then
            result.status_id = 2  -- Failure
        else
            result.status_id = 99 -- Other
        end
    end

    -- Create observables array
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
    if result.actor and result.actor.user and result.actor.user.name then
        table.insert(observables, {
            type_id = 4,
            type = "User Name",
            name = "actor.user.name", 
            value = result.actor.user.name
        })
    end
    if #observables > 0 then
        result.observables = observables
    end
    mappedPaths["observables"] = true

    -- Mark OCSF fields as mapped to avoid duplication
    mappedPaths["class_uid"] = true
    mappedPaths["type_uid"] = true
    mappedPaths["class_name"] = true
    mappedPaths["type_name"] = true

    -- Copy unmapped fields
    copyUnmappedFields(event, mappedPaths, result)

    return result
end