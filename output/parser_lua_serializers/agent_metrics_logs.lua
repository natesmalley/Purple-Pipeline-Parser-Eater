-- Constants for OCSF Process Activity class
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

-- Convert ISO timestamp to milliseconds since epoch
function parseTimestamp(timeStr)
    if not timeStr then return nil end
    local yr, mo, dy, hr, mn, sc = timeStr:match("(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)")
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

-- Map error codes to severity levels
function getSeverityId(errorCode, errorMessage)
    if errorCode then
        -- Critical errors
        if errorCode:match("AccessDenied") or errorCode:match("Forbidden") then
            return 5 -- Critical
        end
        -- High severity errors
        if errorCode:match("Unauthorized") or errorCode:match("InvalidUser") then
            return 4 -- High
        end
        -- Medium severity errors
        if errorCode:match("InvalidParameter") or errorCode:match("ValidationException") then
            return 3 -- Medium
        end
        -- Any other error
        return 2 -- Low
    end
    -- No error means informational
    return 1 -- Informational
end

-- Determine activity based on event context
function getActivityInfo(event)
    local activityId = 99 -- Other by default
    local activityName = "Unknown Process Activity"
    
    -- Check for specific event patterns
    local eventCategory = getNestedField(event, 'eventCategory')
    local errorCode = getNestedField(event, 'errorCode')
    local instanceId = getNestedField(event, 'requestParameters.instanceId')
    
    if instanceId then
        if errorCode then
            activityId = 4 -- Terminate
            activityName = "Process Termination"
        else
            activityId = 1 -- Launch
            activityName = "Process Launch"
        end
    elseif eventCategory == "Management" then
        activityId = 2 -- Create
        activityName = "Process Create"
    elseif errorCode then
        activityId = 4 -- Terminate
        activityName = "Process Error"
    end
    
    return activityId, activityName
end

-- Field mappings table-driven approach
local fieldMappings = {
    -- Direct field mappings
    {type = "direct", source = "message", target = "message"},
    {type = "direct", source = "eventID", target = "uid"},
    {type = "direct", source = "sourceIPAddress", target = "src_endpoint.ip"},
    {type = "direct", source = "userAgent", target = "http_request.user_agent"},
    {type = "direct", source = "errorMessage", target = "status_detail"},
    {type = "direct", source = "errorCode", target = "status"},
    {type = "direct", source = "awsRegion", target = "cloud.region"},
    {type = "direct", source = "recipientAccountId", target = "cloud.account.uid"},
    {type = "direct", source = "apiVersion", target = "api.version"},
    {type = "direct", source = "vpcEndpointId", target = "cloud.zone"},
    {type = "direct", source = "requestParameters.instanceId", target = "process.pid"},
    {type = "direct", source = "requestParameters.bucketName", target = "process.name"},
    {type = "direct", source = "requestParameters.availabilityZone", target = "cloud.availability_zone"},
    
    -- User identity mappings with priority fallback
    {type = "priority", source1 = "userIdentity.sessionContext.sessionIssuer.userName", 
     source2 = "userIdentity.principalId", target = "actor.user.name"},
    {type = "direct", source = "userIdentity.accessKeyId", target = "actor.user.uid"},
    {type = "direct", source = "userIdentity.type", target = "actor.user.type"},
    {type = "direct", source = "userIdentity.invokedBy", target = "actor.invoked_by"},
    
    -- TLS details
    {type = "direct", source = "tlsDetails.cipherSuite", target = "tls.cipher"},
    {type = "direct", source = "tlsDetails.tlsVersion", target = "tls.version"},
    
    -- Response elements
    {type = "direct", source = "responseElements.credentials.accessKeyId", target = "api.response.data"},
    {type = "direct", source = "responseElements.credentials.expiration", target = "end_time"},
    
    -- Resources
    {type = "direct", source = "resources.accountId", target = "resource.account_uid"},
    {type = "direct", source = "resources.type", target = "resource.type"},
    {type = "direct", source = "resources.ARN", target = "resource.uid"},
    
    -- Computed/constant values
    {type = "computed", target = "class_uid", value = CLASS_UID},
    {type = "computed", target = "category_uid", value = CATEGORY_UID},
    {type = "computed", target = "class_name", value = "Process Activity"},
    {type = "computed", target = "category_name", value = "System Activity"},
    {type = "computed", target = "metadata.product.name", value = "AWS Agent Metrics"},
    {type = "computed", target = "metadata.product.vendor_name", value = "Amazon Web Services"}
}

function processEvent(event)
    -- Validate input event
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
    
    -- Set activity information
    local activityId, activityName = getActivityInfo(event)
    result.activity_id = activityId
    result.activity_name = activityName
    
    -- Compute type_uid
    result.type_uid = CLASS_UID * 100 + activityId
    
    -- Set severity based on error conditions
    local errorCode = getNestedField(event, 'errorCode')
    local errorMessage = getNestedField(event, 'errorMessage')
    result.severity_id = getSeverityId(errorCode, errorMessage)
    
    -- Set status_id based on error presence
    if errorCode then
        result.status_id = 2 -- Failure
    else
        result.status_id = 1 -- Success
    end
    
    -- Parse and set timestamp
    local eventTime = getNestedField(event, 'eventTime')
    local parsedTime = parseTimestamp(eventTime)
    result.time = parsedTime or (os.time() * 1000)
    
    -- Set start_time if available
    if parsedTime then
        result.start_time = parsedTime
    end
    
    -- Handle process file information if instanceId is present
    local instanceId = getNestedField(event, 'requestParameters.instanceId')
    if instanceId then
        setNestedField(result, "process.file.name", "instance-" .. instanceId)
        setNestedField(result, "process.file.path", "/aws/instances/" .. instanceId)
    end
    
    -- Add observables for enrichment
    local observables = {}
    local sourceIP = getNestedField(event, 'sourceIPAddress')
    if sourceIP then
        table.insert(observables, {
            type_id = 2,
            type = "IP Address",
            name = "src_endpoint.ip",
            value = sourceIP
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
    
    -- Mark tracked paths for unmapped field collection
    mappedPaths["eventTime"] = true
    mappedPaths["eventVersion"] = true
    mappedPaths["eventCategory"] = true
    mappedPaths["additionalEventData.x-amz-id-2"] = true
    
    -- Collect unmapped fields
    copyUnmappedFields(event, mappedPaths, result)
    
    -- Clean up nil values and empty tables
    result = no_nulls(result, nil)
    
    return result
end