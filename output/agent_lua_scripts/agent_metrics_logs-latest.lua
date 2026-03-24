-- Constants
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

-- Severity mapping for AWS CloudTrail events
local function getSeverityId(eventCategory, errorCode, errorMessage)
    -- Check for errors first
    if errorCode or errorMessage then
        return 4 -- High severity for errors
    end
    
    -- Map based on event category
    if eventCategory then
        local category = string.lower(tostring(eventCategory))
        if string.find(category, "management") then
            return 3 -- Medium for management events
        elseif string.find(category, "data") then
            return 2 -- Low for data events
        elseif string.find(category, "insight") then
            return 1 -- Informational for insight events
        end
    end
    
    return 0 -- Unknown by default
end

-- Convert ISO timestamp to milliseconds since epoch
local function parseTimestamp(timeStr)
    if not timeStr or type(timeStr) ~= "string" then
        return os.time() * 1000
    end
    
    -- Parse ISO 8601 format: YYYY-MM-DDTHH:MM:SS.sssZ
    local year, month, day, hour, min, sec = timeStr:match("(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)")
    if year then
        local timestamp = os.time({
            year = tonumber(year),
            month = tonumber(month),
            day = tonumber(day),
            hour = tonumber(hour),
            min = tonumber(min),
            sec = tonumber(sec),
            isdst = false
        })
        return timestamp * 1000
    end
    
    return os.time() * 1000
end

-- Field mappings configuration
local fieldMappings = {
    -- OCSF required fields (computed)
    {type = "computed", target = "class_uid", value = CLASS_UID},
    {type = "computed", target = "category_uid", value = CATEGORY_UID},
    {type = "computed", target = "class_name", value = "Process Activity"},
    {type = "computed", target = "category_name", value = "System Activity"},
    
    -- Direct mappings
    {type = "direct", source = "message", target = "message"},
    {type = "direct", source = "sourceIPAddress", target = "src_endpoint.ip"},
    {type = "direct", source = "userAgent", target = "http_request.user_agent"},
    {type = "direct", source = "awsRegion", target = "cloud.region"},
    {type = "direct", source = "recipientAccountId", target = "cloud.account.uid"},
    {type = "direct", source = "errorCode", target = "status_detail"},
    {type = "direct", source = "errorMessage", target = "status_detail"},
    {type = "direct", source = "apiVersion", target = "metadata.version"},
    {type = "direct", source = "vpcEndpointId", target = "cloud.vpc_uid"},
    
    -- User identity mappings
    {type = "direct", source = "userIdentity.principalId", target = "actor.user.uid"},
    {type = "direct", source = "userIdentity.accessKeyId", target = "actor.user.credential_uid"},
    {type = "direct", source = "userIdentity.type", target = "actor.user.type"},
    {type = "direct", source = "userIdentity.sessionContext.sessionIssuer.userName", target = "actor.user.name"},
    
    -- Request/Response parameters as process details
    {type = "direct", source = "requestParameters.instanceId", target = "process.uid"},
    {type = "direct", source = "requestParameters.bucketName", target = "process.name"},
    {type = "direct", source = "requestParameters.Host", target = "process.file.name"},
    {type = "direct", source = "requestParameters.availabilityZone", target = "process.file.path"},
    
    -- TLS details
    {type = "direct", source = "tlsDetails.cipherSuite", target = "tls.cipher"},
    {type = "direct", source = "tlsDetails.tlsVersion", target = "tls.version"},
    
    -- Additional event data
    {type = "direct", source = "additionalEventData.x-amz-id-2", target = "metadata.correlation_uid"},
}

function processEvent(event)
    -- Input validation
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

    -- Set activity information based on event
    local eventID = getNestedField(event, "eventID") or "unknown"
    local eventCategory = getNestedField(event, "eventCategory")
    local activityName = eventID
    
    -- Determine activity_id based on event characteristics
    local activityId = 99 -- Other by default
    if eventID then
        local eventIdLower = string.lower(tostring(eventID))
        if string.find(eventIdLower, "create") then
            activityId = 1 -- Create
            activityName = "Process Create"
        elseif string.find(eventIdLower, "start") then
            activityId = 1 -- Start
            activityName = "Process Start"
        elseif string.find(eventIdLower, "terminate") or string.find(eventIdLower, "stop") then
            activityId = 2 -- Terminate
            activityName = "Process Terminate"
        elseif string.find(eventIdLower, "run") or string.find(eventIdLower, "execute") then
            activityId = 3 -- Execute
            activityName = "Process Execute"
        end
    end

    result.activity_id = activityId
    result.activity_name = activityName
    result.type_uid = CLASS_UID * 100 + activityId

    -- Set severity based on event characteristics
    local errorCode = getNestedField(event, "errorCode")
    local errorMessage = getNestedField(event, "errorMessage")
    result.severity_id = getSeverityId(eventCategory, errorCode, errorMessage)

    -- Set status based on errors
    if errorCode or errorMessage then
        result.status = "Failure"
        result.status_id = 2 -- Failure
    else
        result.status = "Success"
        result.status_id = 1 -- Success
    end

    -- Set timestamp
    local eventTime = getNestedField(event, "eventTime")
    result.time = parseTimestamp(eventTime)

    -- Set metadata
    setNestedField(result, "metadata.product.name", "Agent Metrics")
    setNestedField(result, "metadata.product.vendor_name", "Unknown")

    -- Add raw data
    result.raw_data = event.message or ""

    -- Handle resources array if present
    local resources = getNestedField(event, "resources")
    if resources and type(resources) == "table" then
        for i, resource in ipairs(resources) do
            if resource.ARN then
                setNestedField(result, "process.file.path", resource.ARN)
                mappedPaths["resources"] = true
                break
            end
        end
    end

    -- Copy unmapped fields to preserve data
    copyUnmappedFields(event, mappedPaths, result)

    -- Clean up userdata nulls
    result = no_nulls(result, nil)

    return result
end