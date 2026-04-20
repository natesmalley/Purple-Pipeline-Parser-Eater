-- Apache HTTP Logs to OCSF HTTP Activity transformation
local CLASS_UID = 4002
local CATEGORY_UID = 4

-- HTTP status code to severity mapping
local function getSeverityFromStatus(statusCode)
    if not statusCode then return 0 end
    local code = tonumber(statusCode)
    if not code then return 0 end
    
    if code >= 500 then return 5      -- Critical: Server errors
    elseif code >= 400 then return 3  -- Medium: Client errors  
    elseif code >= 300 then return 2  -- Low: Redirects
    elseif code >= 200 then return 1  -- Informational: Success
    else return 0 end                 -- Unknown
end

-- Extract HTTP method from message or user agent
local function extractHttpMethod(message, userAgent)
    if message then
        local method = message:match('^"?([A-Z]+)%s')
        if method then return method end
    end
    return nil
end

-- Extract URL from message
local function extractUrl(message)
    if message then
        local url = message:match('^"?[A-Z]+%s+([^%s]+)')
        if url then return url end
    end
    return nil
end

-- Extract HTTP version from message
local function extractHttpVersion(message)
    if message then
        local version = message:match('HTTP/([%d%.]+)')
        if version then return version end
    end
    return nil
end

-- Extract status code from message
local function extractStatusCode(message)
    if message then
        -- Look for status code pattern (3 digits)
        local code = message:match('%s+(%d%d%d)%s+')
        if code then return tonumber(code) end
    end
    return nil
end

-- Nested field access
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

-- Collect unmapped fields
function copyUnmappedFields(event, mappedPaths, result)
    for k, v in pairs(event) do
        if not mappedPaths[k] and k ~= "_ob" and v ~= nil and v ~= "" then
            setNestedField(result, "unmapped." .. k, v)
        end
    end
end

-- Field mappings for Apache HTTP logs
local fieldMappings = {
    -- OCSF required fields
    {type = "computed", target = "class_uid", value = CLASS_UID},
    {type = "computed", target = "category_uid", value = CATEGORY_UID},
    {type = "computed", target = "class_name", value = "HTTP Activity"},
    {type = "computed", target = "category_name", value = "Network Activity"},
    
    -- Direct mappings
    {type = "direct", source = "sourceIPAddress", target = "src_endpoint.ip"},
    {type = "direct", source = "userAgent", target = "http_request.user_agent"},
    {type = "direct", source = "message", target = "message"},
    {type = "direct", source = "eventID", target = "uid"},
    {type = "direct", source = "awsRegion", target = "cloud.region"},
    
    -- Host information
    {type = "direct", source = "requestParameters.Host", target = "dst_endpoint.hostname"},
    {type = "direct", source = "requestParameters.bucketName", target = "http_request.url.hostname"},
    
    -- TLS details
    {type = "direct", source = "tlsDetails.tlsVersion", target = "tls.version"},
    {type = "direct", source = "tlsDetails.cipherSuite", target = "tls.cipher"},
    
    -- User identity
    {type = "priority", source1 = "userIdentity.sessionContext.sessionIssuer.userName", 
     source2 = "userIdentity.principalId", target = "actor.user.name"},
    {type = "direct", source = "userIdentity.type", target = "actor.user.type"},
    {type = "direct", source = "userIdentity.accessKeyId", target = "actor.user.credential_uid"},
    
    -- Error information
    {type = "direct", source = "errorCode", target = "status_code"},
    {type = "direct", source = "errorMessage", target = "status_detail"},
    
    -- Metadata
    {type = "computed", target = "metadata.product.name", value = "Apache HTTP Server"},
    {type = "direct", source = "apiVersion", target = "metadata.version"},
}

function processEvent(event)
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
            if (value == nil or value == "") and mapping.source2 then 
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
    
    -- Extract HTTP details from message field
    local message = event.message
    if message then
        local httpMethod = extractHttpMethod(message, event.userAgent)
        if httpMethod then
            result.http_request = result.http_request or {}
            result.http_request.http_method = httpMethod
        end
        
        local url = extractUrl(message)
        if url then
            result.http_request = result.http_request or {}
            result.http_request.url = result.http_request.url or {}
            result.http_request.url.url_string = url
        end
        
        local httpVersion = extractHttpVersion(message)
        if httpVersion then
            result.http_request = result.http_request or {}
            result.http_request.version = httpVersion
        end
        
        local statusCode = extractStatusCode(message)
        if statusCode then
            result.http_response = result.http_response or {}
            result.http_response.code = statusCode
            result.status_id = statusCode < 400 and 1 or 2  -- 1=Success, 2=Failure
            
            -- Set severity based on status code
            result.severity_id = getSeverityFromStatus(statusCode)
        end
    end
    
    -- Set activity based on HTTP method or error
    local activityId = 99  -- Other
    local activityName = "HTTP Request"
    
    if event.errorCode or event.errorMessage then
        activityId = 2  -- HTTP Error
        activityName = "HTTP Error"
    elseif result.http_request and result.http_request.http_method then
        local method = result.http_request.http_method
        if method == "GET" then
            activityId = 1
            activityName = "HTTP GET"
        elseif method == "POST" then
            activityId = 3
            activityName = "HTTP POST" 
        elseif method == "PUT" then
            activityId = 4
            activityName = "HTTP PUT"
        elseif method == "DELETE" then
            activityId = 5
            activityName = "HTTP DELETE"
        else
            activityId = 99
            activityName = "HTTP " .. method
        end
    end
    
    result.activity_id = activityId
    result.activity_name = activityName
    result.type_uid = CLASS_UID * 100 + activityId
    
    -- Set defaults for required fields
    if not result.severity_id then result.severity_id = 1 end  -- Informational default
    if not result.status_id then result.status_id = 0 end     -- Unknown
    
    -- Convert eventTime to milliseconds since epoch
    local eventTime = event.eventTime
    if eventTime then
        -- Parse ISO 8601 format: 2023-05-15T10:30:45Z
        local year, month, day, hour, min, sec = eventTime:match("(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)")
        if year then
            result.time = os.time({
                year = tonumber(year),
                month = tonumber(month),
                day = tonumber(day),
                hour = tonumber(hour),
                min = tonumber(min),
                sec = tonumber(sec),
                isdst = false
            }) * 1000
        else
            result.time = os.time() * 1000
        end
    else
        result.time = os.time() * 1000
    end
    
    -- Mark additional mapped paths
    mappedPaths["message"] = true
    mappedPaths["eventTime"] = true
    
    -- Copy unmapped fields
    copyUnmappedFields(event, mappedPaths, result)
    
    -- Create observables for key indicators
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
            type_id = 6,
            type = "User Agent",
            name = "http_request.user_agent", 
            value = event.userAgent
        })
    end
    if #observables > 0 then
        result.observables = observables
    end
    
    return result
end