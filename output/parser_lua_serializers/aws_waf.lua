-- AWS WAF Log Parser - Transforms AWS WAF events to OCSF HTTP Activity format
-- Class: HTTP Activity (4002), Category: Network Activity (4)

-- Constants
local CLASS_UID = 4002
local CATEGORY_UID = 4

-- Field mappings configuration
local fieldMappings = {
    -- Direct mappings
    {type = "direct", source = "sourceIPAddress", target = "src_endpoint.ip"},
    {type = "direct", source = "userAgent", target = "http_request.user_agent"},
    {type = "direct", source = "awsRegion", target = "cloud.region"},
    {type = "direct", source = "recipientAccountId", target = "cloud.account.uid"},
    {type = "direct", source = "eventID", target = "metadata.uid"},
    {type = "direct", source = "eventVersion", target = "metadata.version"},
    {type = "direct", source = "message", target = "message"},
    {type = "direct", source = "errorCode", target = "status_code"},
    {type = "direct", source = "errorMessage", target = "status_detail"},
    {type = "direct", source = "apiVersion", target = "api.version"},
    {type = "direct", source = "vpcEndpointId", target = "cloud.vpc_uid"},
    
    -- HTTP request mappings
    {type = "direct", source = "requestParameters.Host", target = "http_request.url.hostname"},
    {type = "direct", source = "requestParameters.bucketName", target = "http_request.url.path"},
    
    -- TLS details
    {type = "direct", source = "tlsDetails.cipherSuite", target = "tls.cipher"},
    {type = "direct", source = "tlsDetails.tlsVersion", target = "tls.version"},
    
    -- User identity mappings
    {type = "direct", source = "userIdentity.principalId", target = "actor.user.uid"},
    {type = "direct", source = "userIdentity.accessKeyId", target = "actor.user.credential_uid"},
    {type = "direct", source = "userIdentity.type", target = "actor.user.type"},
    {type = "priority", source1 = "userIdentity.sessionContext.sessionIssuer.userName", source2 = "userIdentity.sessionContext.sessionIssuer.principalId", target = "actor.user.name"},
    
    -- Computed/static values
    {type = "computed", target = "class_uid", value = CLASS_UID},
    {type = "computed", target = "category_uid", value = CATEGORY_UID},
    {type = "computed", target = "class_name", value = "HTTP Activity"},
    {type = "computed", target = "category_name", value = "Network Activity"},
    {type = "computed", target = "metadata.product.name", value = "AWS WAF"},
    {type = "computed", target = "metadata.product.vendor_name", value = "Amazon Web Services"},
}

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

-- Collect unmapped fields
function copyUnmappedFields(event, mappedPaths, result)
    local function addToUnmapped(obj, prefix)
        if type(obj) ~= "table" then return end
        for k, v in pairs(obj) do
            if type(v) == "table" then
                addToUnmapped(v, prefix .. k .. ".")
            else
                local fullPath = prefix .. k
                if not mappedPaths[fullPath] and k ~= "_ob" and v ~= nil and v ~= "" then
                    if not result.unmapped then result.unmapped = {} end
                    result.unmapped[fullPath] = v
                end
            end
        end
    end
    addToUnmapped(event, "")
end

-- Convert ISO timestamp to milliseconds
function parseTimestamp(timeStr)
    if not timeStr or timeStr == "" then return nil end
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

-- Determine severity based on event data
function getSeverityId(event)
    -- Check for error conditions
    if event.errorCode or event.errorMessage then
        return 4 -- High severity for errors
    end
    
    -- Check event category for severity hints
    local category = event.eventCategory
    if category then
        if category:lower():find("error") or category:lower():find("fail") then
            return 4 -- High
        elseif category:lower():find("warn") then
            return 3 -- Medium
        end
    end
    
    return 1 -- Informational by default for HTTP activity
end

-- Determine activity based on event data
function getActivityInfo(event)
    local activityId = 99 -- Other by default
    local activityName = "HTTP Request"
    
    -- Try to determine HTTP method or operation
    if event.requestParameters and event.requestParameters.Host then
        activityName = "HTTP Request to " .. event.requestParameters.Host
        activityId = 1 -- HTTP Request
    elseif event.errorCode then
        activityName = "HTTP Error: " .. event.errorCode
        activityId = 2 -- HTTP Response
    end
    
    return activityId, activityName
end

-- Main processing function
function processEvent(event)
    -- Validate input
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
            if mapping.source2 then mappedPaths[mapping.source2] = true end
            
        elseif mapping.type == "computed" then
            setNestedField(result, mapping.target, mapping.value)
        end
    end
    
    -- Set required OCSF fields
    local activityId, activityName = getActivityInfo(event)
    result.activity_id = activityId
    result.activity_name = activityName
    result.type_uid = CLASS_UID * 100 + activityId
    result.severity_id = getSeverityId(event)
    
    -- Set timestamp
    local eventTime = event.eventTime
    if eventTime then
        result.time = parseTimestamp(eventTime)
    end
    if not result.time then
        result.time = os.time() * 1000
    end
    
    -- Mark timestamp fields as mapped
    mappedPaths["eventTime"] = true
    
    -- Set HTTP response code if error code present
    if event.errorCode then
        if not result.http_response then result.http_response = {} end
        -- Map common error codes to HTTP status codes
        local httpCode = 500 -- Default server error
        if event.errorCode == "AccessDenied" then httpCode = 403
        elseif event.errorCode == "NoSuchBucket" then httpCode = 404
        elseif event.errorCode == "InvalidRequest" then httpCode = 400
        end
        result.http_response.code = httpCode
        result.http_response.message = event.errorMessage or event.errorCode
    end
    
    -- Add observables for enrichment
    local observables = {}
    if event.sourceIPAddress then
        table.insert(observables, {
            type_id = 2,
            type = "IP Address",
            name = "src_endpoint.ip",
            value = event.sourceIPAddress
        })
    end
    if event.userAgent then
        table.insert(observables, {
            type_id = 7,
            type = "User Agent",
            name = "http_request.user_agent",
            value = event.userAgent
        })
    end
    if #observables > 0 then
        result.observables = observables
    end
    
    -- Copy unmapped fields
    copyUnmappedFields(event, mappedPaths, result)
    
    return result
end