-- Okta Authentication Logs to OCSF Authentication Class Transformer
-- Class UID: 3002 (Authentication)
-- Category UID: 3 (Identity & Access Management)

local CLASS_UID = 3002
local CATEGORY_UID = 3

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

-- Convert ISO timestamp to milliseconds since epoch
local function parseTimestamp(timeStr)
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

-- Map event category to activity_id and activity_name
local function getActivityMapping(eventCategory, errorCode)
    if errorCode then
        return 2, "Logon" -- Authentication failure
    end
    
    -- Default mappings for common authentication activities
    local categoryMap = {
        ["authentication"] = {1, "Logon"},
        ["signin"] = {1, "Logon"},
        ["login"] = {1, "Logon"},
        ["logout"] = {2, "Logoff"},
        ["signout"] = {2, "Logoff"}
    }
    
    if eventCategory and categoryMap[string.lower(eventCategory)] then
        return categoryMap[string.lower(eventCategory)][1], categoryMap[string.lower(eventCategory)][2]
    end
    
    return 99, "Other" -- Unknown activity
end

-- Determine severity based on error conditions
local function getSeverityId(errorCode, errorMessage)
    if errorCode or errorMessage then
        return 4 -- High - authentication failures are security relevant
    end
    return 1 -- Informational - successful authentication
end

-- Main transformation function
function processEvent(event)
    if type(event) ~= "table" then return nil end
    
    local result = {}
    local mappedPaths = {}
    
    -- Field mappings configuration
    local fieldMappings = {
        -- Core OCSF fields
        {type = "computed", target = "class_uid", value = CLASS_UID},
        {type = "computed", target = "category_uid", value = CATEGORY_UID},
        {type = "computed", target = "class_name", value = "Authentication"},
        {type = "computed", target = "category_name", value = "Identity & Access Management"},
        
        -- User identity mappings
        {type = "priority", source1 = "userIdentity.sessionContext.sessionIssuer.userName", 
         source2 = "userIdentity.principalId", target = "actor.user.name"},
        {type = "direct", source = "userIdentity.principalId", target = "actor.user.uid"},
        {type = "direct", source = "userIdentity.accessKeyId", target = "actor.user.credential_uid"},
        {type = "direct", source = "userIdentity.type", target = "actor.user.type"},
        
        -- Network information
        {type = "direct", source = "sourceIPAddress", target = "src_endpoint.ip"},
        {type = "direct", source = "userAgent", target = "src_endpoint.user_agent"},
        
        -- Request details
        {type = "direct", source = "requestParameters.Host", target = "dst_endpoint.hostname"},
        
        -- Error information
        {type = "direct", source = "errorCode", target = "status_code"},
        {type = "direct", source = "errorMessage", target = "status_detail"},
        
        -- Event metadata
        {type = "direct", source = "eventID", target = "uid"},
        {type = "direct", source = "eventVersion", target = "metadata.version"},
        {type = "direct", source = "awsRegion", target = "cloud.region"},
        {type = "direct", source = "recipientAccountId", target = "cloud.account.uid"},
        {type = "direct", source = "apiVersion", target = "api.version"},
        {type = "direct", source = "message", target = "message"},
        
        -- TLS details
        {type = "direct", source = "tlsDetails.cipherSuite", target = "tls.cipher"},
        {type = "direct", source = "tlsDetails.tlsVersion", target = "tls.version"},
        
        -- VPC information
        {type = "direct", source = "vpcEndpointId", target = "cloud.vpc_uid"}
    }
    
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
    
    -- Handle timestamp conversion
    local eventTime = getNestedField(event, 'eventTime')
    if eventTime then
        local timeMs = parseTimestamp(eventTime)
        if timeMs then
            result.time = timeMs
        else
            result.time = os.time() * 1000 -- Fallback to current time
        end
        mappedPaths['eventTime'] = true
    else
        result.time = os.time() * 1000
    end
    
    -- Determine activity and severity
    local errorCode = getNestedField(event, 'errorCode')
    local errorMessage = getNestedField(event, 'errorMessage')
    local eventCategory = getNestedField(event, 'eventCategory')
    
    local activityId, activityName = getActivityMapping(eventCategory, errorCode)
    result.activity_id = activityId
    result.activity_name = activityName
    result.type_uid = CLASS_UID * 100 + activityId
    result.severity_id = getSeverityId(errorCode, errorMessage)
    
    mappedPaths['eventCategory'] = true
    
    -- Set authentication status
    if errorCode or errorMessage then
        result.status = "Failure"
        result.status_id = 2 -- Failure
    else
        result.status = "Success"
        result.status_id = 1 -- Success
    end
    
    -- Set product metadata
    setNestedField(result, "metadata.product.name", "Okta")
    setNestedField(result, "metadata.product.vendor_name", "Okta")
    
    -- Handle resources array
    local resources = getNestedField(event, 'resources')
    if resources and type(resources) == "table" then
        if #resources > 0 then
            local resource = resources[1]
            if resource.accountId then
                setNestedField(result, "cloud.account.uid", resource.accountId)
            end
            if resource.ARN then
                setNestedField(result, "resource.uid", resource.ARN)
            end
            if resource.type then
                setNestedField(result, "resource.type", resource.type)
            end
        end
        mappedPaths['resources'] = true
    end
    
    -- Handle additional event data
    local additionalData = getNestedField(event, 'additionalEventData')
    if additionalData and type(additionalData) == "table" then
        for k, v in pairs(additionalData) do
            setNestedField(result, "metadata.additional." .. k, v)
        end
        mappedPaths['additionalEventData'] = true
    end
    
    -- Copy unmapped fields to preserve data
    copyUnmappedFields(event, mappedPaths, result)
    
    return result
end