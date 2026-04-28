-- OCSF Network Activity transformation for windows_event_log_logs-latest
-- Maps Windows Event Log data to OCSF Network Activity (class_uid=4001)

local CLASS_UID = 4001
local CATEGORY_UID = 4

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
    if type(tbl) ~= "table" then return default end
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

-- Convert ISO timestamp to milliseconds since epoch
function parseTimestamp(timeStr)
    if not timeStr or type(timeStr) ~= "string" then return nil end
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

-- Map event category to OCSF activity_id
function getActivityId(eventCategory)
    if not eventCategory then return 99 end
    local activityMap = {
        ["Management"] = 1,
        ["Data"] = 2,
        ["Read"] = 1,
        ["Write"] = 2,
        ["Permissions"] = 3
    }
    return activityMap[eventCategory] or 99
end

-- Map error conditions to severity
function getSeverityId(errorCode, errorMessage)
    if errorCode or errorMessage then
        return 4 -- High severity for errors
    end
    return 1 -- Informational for normal operations
end

-- Get activity name based on event context
function getActivityName(event)
    local eventCategory = getNestedField(event, "eventCategory")
    local eventID = getNestedField(event, "eventID")
    
    if eventCategory then
        return eventCategory .. " Activity"
    elseif eventID then
        return "Event ID " .. tostring(eventID)
    else
        return "Network Activity"
    end
end

-- Field mappings configuration
local fieldMappings = {
    -- Core OCSF fields
    {type = "computed", target = "class_uid", value = CLASS_UID},
    {type = "computed", target = "category_uid", value = CATEGORY_UID},
    {type = "computed", target = "class_name", value = "Network Activity"},
    {type = "computed", target = "category_name", value = "Network Activity"},
    
    -- Network endpoints
    {type = "direct", source = "sourceIPAddress", target = "src_endpoint.ip"},
    {type = "direct", source = "requestParameters.Host", target = "dst_endpoint.hostname"},
    
    -- Message and status
    {type = "direct", source = "message", target = "message"},
    {type = "direct", source = "errorCode", target = "status"},
    {type = "direct", source = "errorMessage", target = "status_detail"},
    
    -- Metadata
    {type = "computed", target = "metadata.product.name", value = "Windows Event Log"},
    {type = "computed", target = "metadata.product.vendor_name", value = "Microsoft"},
    {type = "direct", source = "eventVersion", target = "metadata.version"},
    
    -- Protocol details
    {type = "direct", source = "tlsDetails.tlsVersion", target = "tls.version"},
    {type = "direct", source = "tlsDetails.cipherSuite", target = "tls.cipher"},
    
    -- User information
    {type = "priority", source1 = "userIdentity.sessionContext.sessionIssuer.userName", 
     source2 = "userIdentity.principalId", target = "actor.user.name"},
    {type = "direct", source = "userIdentity.type", target = "actor.user.type"},
    {type = "direct", source = "userIdentity.accessKeyId", target = "actor.user.credential_uid"},
    
    -- Additional context
    {type = "direct", source = "userAgent", target = "http_request.user_agent"},
    {type = "direct", source = "awsRegion", target = "cloud.region"},
    {type = "direct", source = "recipientAccountId", target = "cloud.account.uid"},
    {type = "direct", source = "vpcEndpointId", target = "connection_info.uid"},
    
    -- Resource information
    {type = "direct", source = "resources.ARN", target = "resources.uid"},
    {type = "direct", source = "resources.type", target = "resources.type"},
    {type = "direct", source = "resources.accountId", target = "resources.account_uid"},
    
    -- Request parameters
    {type = "direct", source = "requestParameters.bucketName", target = "http_request.referrer"},
    {type = "direct", source = "requestParameters.instanceId", target = "dst_endpoint.instance_uid"},
    {type = "direct", source = "requestParameters.availabilityZone", target = "dst_endpoint.location.region"},
    
    -- Response elements
    {type = "direct", source = "responseElements.credentials.accessKeyId", target = "http_response.headers.x-access-key"},
    {type = "direct", source = "responseElements.credentials.expiration", target = "end_time_dt"},
    
    -- Additional event data
    {type = "direct", source = "additionalEventData.x-amz-id-2", target = "http_request.headers.x-amz-id-2"}
}

function processEvent(event)
    -- Validate input
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
            if not value or value == "" then
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
    
    -- Set activity_id and compute type_uid
    local activityId = getActivityId(getNestedField(event, "eventCategory"))
    result.activity_id = activityId
    result.type_uid = CLASS_UID * 100 + activityId
    
    -- Set activity name
    result.activity_name = getActivityName(event)
    
    -- Set severity based on error conditions
    result.severity_id = getSeverityId(
        getNestedField(event, "errorCode"),
        getNestedField(event, "errorMessage")
    )
    
    -- Handle timestamp conversion
    local eventTime = getNestedField(event, "eventTime")
    if eventTime then
        local timestamp = parseTimestamp(eventTime)
        if timestamp then
            result.time = timestamp
        end
    end
    
    -- Set current time if no event time found
    if not result.time then
        result.time = os.time() * 1000
    end
    
    -- Add status_id based on error presence
    if getNestedField(event, "errorCode") or getNestedField(event, "errorMessage") then
        result.status_id = 2 -- Failure
    else
        result.status_id = 1 -- Success
    end
    
    -- Mark additional mapped paths
    local additionalPaths = {
        "eventCategory", "eventID", "eventTime", "eventVersion", "errorCode", "errorMessage"
    }
    for _, path in ipairs(additionalPaths) do
        mappedPaths[path] = true
    end
    
    -- Preserve unmapped fields
    copyUnmappedFields(event, mappedPaths, result)
    
    return result
end