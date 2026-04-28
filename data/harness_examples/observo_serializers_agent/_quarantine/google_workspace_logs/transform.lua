-- Google Workspace Logs to OCSF Network Activity transformation
-- Class UID: 4001 (Network Activity), Category UID: 4 (Network Activity)

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

-- Set nested field helper
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
    local year, month, day, hour, min, sec = timeStr:match("(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)")
    if year then
        return os.time({
            year = tonumber(year),
            month = tonumber(month),
            day = tonumber(day),
            hour = tonumber(hour),
            min = tonumber(min),
            sec = tonumber(sec),
            isdst = false
        }) * 1000
    end
    return nil
end

-- Map severity from error codes and event categories
function getSeverityId(errorCode, eventCategory)
    if errorCode then
        -- Error conditions are typically high severity
        if errorCode:match("AccessDenied") or errorCode:match("Forbidden") then
            return 4 -- High
        elseif errorCode:match("Unauthorized") then
            return 3 -- Medium
        else
            return 2 -- Low (other errors)
        end
    end
    
    if eventCategory then
        if eventCategory:match("Data") or eventCategory:match("Management") then
            return 3 -- Medium
        end
    end
    
    return 1 -- Informational (default)
end

-- Get activity name from event data
function getActivityName(event)
    if event.eventID then
        return event.eventID
    elseif event.eventCategory then
        return event.eventCategory .. " Activity"
    else
        return "Network Activity"
    end
end

-- Field mappings configuration
local fieldMappings = {
    -- OCSF Required fields
    {type = "computed", target = "class_uid", value = CLASS_UID},
    {type = "computed", target = "category_uid", value = CATEGORY_UID},
    {type = "computed", target = "class_name", value = "Network Activity"},
    {type = "computed", target = "category_name", value = "Network Activity"},
    
    -- Network endpoint mapping
    {type = "direct", source = "sourceIPAddress", target = "src_endpoint.ip"},
    {type = "direct", source = "requestParameters.Host", target = "dst_endpoint.hostname"},
    
    -- User identity mapping
    {type = "priority", source1 = "userIdentity.sessionContext.sessionIssuer.userName", 
     source2 = "userIdentity.principalId", target = "actor.user.name"},
    {type = "direct", source = "userIdentity.type", target = "actor.user.type"},
    {type = "direct", source = "userIdentity.accessKeyId", target = "actor.user.credential_uid"},
    
    -- Metadata mapping
    {type = "computed", target = "metadata.product.name", value = "Google Workspace"},
    {type = "computed", target = "metadata.product.vendor_name", value = "Google"},
    {type = "direct", source = "eventVersion", target = "metadata.version"},
    {type = "direct", source = "awsRegion", target = "cloud.region"},
    {type = "direct", source = "recipientAccountId", target = "cloud.account.uid"},
    
    -- Event details
    {type = "direct", source = "message", target = "message"},
    {type = "direct", source = "eventID", target = "uid"},
    {type = "direct", source = "eventCategory", target = "category_name"},
    {type = "direct", source = "userAgent", target = "http_request.user_agent"},
    
    -- Error information
    {type = "direct", source = "errorCode", target = "status_code"},
    {type = "direct", source = "errorMessage", target = "status_detail"},
    
    -- TLS details
    {type = "direct", source = "tlsDetails.tlsVersion", target = "tls.version"},
    {type = "direct", source = "tlsDetails.cipherSuite", target = "tls.cipher"},
    
    -- Resource information
    {type = "direct", source = "resources.ARN", target = "dst_endpoint.uid"},
    {type = "direct", source = "requestParameters.bucketName", target = "dst_endpoint.name"},
    {type = "direct", source = "requestParameters.instanceId", target = "dst_endpoint.instance_uid"},
    
    -- VPC endpoint
    {type = "direct", source = "vpcEndpointId", target = "connection_info.uid"}
}

function processEvent(event)
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

    -- Set activity_id and activity_name
    local activityId = 99 -- Other (default)
    if event.errorCode then
        activityId = 6 -- Deny
    elseif event.eventCategory and event.eventCategory:match("Data") then
        activityId = 5 -- Access
    else
        activityId = 1 -- Open
    end
    
    result.activity_id = activityId
    result.activity_name = getActivityName(event)
    
    -- Compute type_uid
    result.type_uid = CLASS_UID * 100 + activityId
    
    -- Set severity
    result.severity_id = getSeverityId(event.errorCode, event.eventCategory)
    
    -- Set status based on error presence
    if event.errorCode then
        result.status = "Failure"
        result.status_id = 2
    else
        result.status = "Success"
        result.status_id = 1
    end
    
    -- Parse timestamp
    local eventTime = event.eventTime
    if eventTime then
        local timestamp = parseTimestamp(eventTime)
        if timestamp then
            result.time = timestamp
        else
            result.time = os.time() * 1000
        end
    else
        result.time = os.time() * 1000
    end

    -- Add observables for key network indicators
    local observables = {}
    if event.sourceIPAddress then
        table.insert(observables, {
            type_id = 2,
            type = "IP Address",
            name = "src_endpoint.ip",
            value = event.sourceIPAddress
        })
    end
    if getNestedField(event, "userIdentity.principalId") then
        table.insert(observables, {
            type_id = 4,
            type = "User Name", 
            name = "actor.user.name",
            value = getNestedField(event, "userIdentity.principalId")
        })
    end
    if #observables > 0 then
        result.observables = observables
    end

    -- Mark additional mapped paths for unmapped field collection
    mappedPaths["eventTime"] = true
    mappedPaths["errorCode"] = true
    mappedPaths["errorMessage"] = true
    mappedPaths["userIdentity"] = true
    mappedPaths["requestParameters"] = true
    mappedPaths["responseElements"] = true
    mappedPaths["additionalEventData"] = true
    mappedPaths["tlsDetails"] = true
    mappedPaths["resources"] = true

    -- Copy unmapped fields
    copyUnmappedFields(event, mappedPaths, result)

    return result
end