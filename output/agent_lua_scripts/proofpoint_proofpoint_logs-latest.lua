-- Proofpoint Email Security Logs to OCSF Network Activity transformation
-- Maps Proofpoint threat detection and email security events to OCSF format

-- OCSF Constants
local CLASS_UID = 4001
local CATEGORY_UID = 4
local CLASS_NAME = "Network Activity"
local CATEGORY_NAME = "Network Activity"

-- Helper functions
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
function parseTimestamp(timeStr)
    if not timeStr or timeStr == "" then return nil end
    
    -- Try ISO format: YYYY-MM-DDTHH:MM:SS[.sss][Z|±HH:MM]
    local year, month, day, hour, min, sec = timeStr:match("(%d%d%d%d)-(%d%d)-(%d%d)T(%d%d):(%d%d):(%d%d)")
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
    
    return nil
end

-- Map threat status to severity
function getSeverityFromThreat(threatStatus, classification, spamScore, phishScore, malwareScore)
    -- High severity for active threats
    if threatStatus == "active" or threatStatus == "detected" then return 4 end
    
    -- Check classification for severity hints
    if classification then
        local classLower = string.lower(classification)
        if string.find(classLower, "malware") or string.find(classLower, "virus") then return 5 end
        if string.find(classLower, "phish") then return 4 end
        if string.find(classLower, "spam") then return 2 end
    end
    
    -- Use scores if available (assuming higher scores = higher risk)
    local maxScore = 0
    if malwareScore and tonumber(malwareScore) then maxScore = math.max(maxScore, tonumber(malwareScore)) end
    if phishScore and tonumber(phishScore) then maxScore = math.max(maxScore, tonumber(phishScore)) end
    if spamScore and tonumber(spamScore) then maxScore = math.max(maxScore, tonumber(spamScore)) end
    
    if maxScore >= 80 then return 5 -- Critical
    elseif maxScore >= 60 then return 4 -- High
    elseif maxScore >= 40 then return 3 -- Medium
    elseif maxScore >= 20 then return 2 -- Low
    elseif maxScore > 0 then return 1 -- Informational
    end
    
    return 0 -- Unknown
end

-- Determine activity type and name
function getActivityInfo(event)
    local activityId = 99 -- Other by default
    local activityName = "Email Security Event"
    
    if event.threatStatus or event.threatID or event.threatURL then
        activityId = 1 -- Traffic
        activityName = "Threat Detection"
    elseif event.clickTime or event.clickIP then
        activityId = 5 -- Authorize
        activityName = "URL Click"
    elseif event.quarantineFolder or event.quarantineRule then
        activityId = 2 -- Refuse
        activityName = "Email Quarantine"
    elseif event.messageID then
        activityId = 1 -- Traffic
        activityName = "Email Processing"
    end
    
    return activityId, activityName
end

-- Field mappings configuration
local fieldMappings = {
    -- Direct mappings
    {type = "direct", source = "senderIP", target = "src_endpoint.ip"},
    {type = "direct", source = "clickIP", target = "src_endpoint.ip"},
    {type = "direct", source = "recipient", target = "dst_endpoint.hostname"},
    {type = "direct", source = "sender", target = "actor.user.email_addr"},
    {type = "direct", source = "fromAddress", target = "actor.user.email_addr"},
    {type = "direct", source = "subject", target = "message"},
    {type = "direct", source = "userAgent", target = "http_request.user_agent"},
    {type = "direct", source = "url", target = "http_request.url.url_string"},
    {type = "direct", source = "threatURL", target = "http_request.url.url_string"},
    {type = "direct", source = "messageID", target = "metadata.correlation_uid"},
    {type = "direct", source = "GUID", target = "metadata.uid"},
    {type = "direct", source = "campaignID", target = "attacks.campaign_uid"},
    {type = "direct", source = "threatID", target = "malware.name"},
    {type = "direct", source = "classification", target = "type_name"},
    {type = "direct", source = "QID", target = "connection_info.uid"},
    
    -- Computed values
    {type = "computed", target = "class_uid", value = CLASS_UID},
    {type = "computed", target = "category_uid", value = CATEGORY_UID},
    {type = "computed", target = "class_name", value = CLASS_NAME},
    {type = "computed", target = "category_name", value = CATEGORY_NAME},
    {type = "computed", target = "metadata.product.name", value = "Proofpoint Email Security"},
    {type = "computed", target = "metadata.product.vendor_name", value = "Proofpoint"},
    {type = "computed", target = "protocol_name", value = "SMTP"},
}

function processEvent(event)
    if type(event) ~= "table" then return nil end
    
    local result = {}
    local mappedPaths = {}
    
    -- Process field mappings
    for _, mapping in ipairs(fieldMappings) do
        if mapping.type == "direct" then
            local value = event[mapping.source]
            if value ~= nil and value ~= "" then
                setNestedField(result, mapping.target, value)
            end
            mappedPaths[mapping.source] = true
        elseif mapping.type == "computed" then
            setNestedField(result, mapping.target, mapping.value)
        end
    end
    
    -- Handle priority mappings for source IP (prefer senderIP over clickIP)
    if event.senderIP then
        result.src_endpoint = result.src_endpoint or {}
        result.src_endpoint.ip = event.senderIP
    elseif event.clickIP then
        result.src_endpoint = result.src_endpoint or {}
        result.src_endpoint.ip = event.clickIP
    end
    mappedPaths.senderIP = true
    mappedPaths.clickIP = true
    
    -- Handle priority mappings for email addresses
    if event.sender then
        result.actor = result.actor or {}
        result.actor.user = result.actor.user or {}
        result.actor.user.email_addr = event.sender
    elseif event.fromAddress then
        result.actor = result.actor or {}
        result.actor.user = result.actor.user or {}
        result.actor.user.email_addr = event.fromAddress
    end
    mappedPaths.sender = true
    mappedPaths.fromAddress = true
    
    -- Set activity information
    local activityId, activityName = getActivityInfo(event)
    result.activity_id = activityId
    result.activity_name = activityName
    result.type_uid = CLASS_UID * 100 + activityId
    
    -- Set timestamp - priority: threatTime > clickTime > messageTime > current time
    local timeValue = nil
    if event.threatTime then
        timeValue = parseTimestamp(event.threatTime)
        mappedPaths.threatTime = true
    elseif event.clickTime then
        timeValue = parseTimestamp(event.clickTime)
        mappedPaths.clickTime = true
    elseif event.messageTime then
        timeValue = parseTimestamp(event.messageTime)
        mappedPaths.messageTime = true
    end
    result.time = timeValue or (os.time() * 1000)
    
    -- Set severity based on threat information
    result.severity_id = getSeverityFromThreat(
        event.threatStatus,
        event.classification,
        event.spamScore,
        event.phishScore,
        event.malwareScore
    )
    mappedPaths.threatStatus = true
    mappedPaths.classification = true
    mappedPaths.spamScore = true
    mappedPaths.phishScore = true
    mappedPaths.malwareScore = true
    
    -- Handle email addresses lists
    if event.toAddresses then
        result.email = result.email or {}
        result.email.to = event.toAddresses
        mappedPaths.toAddresses = true
    end
    if event.ccAddresses then
        result.email = result.email or {}
        result.email.cc = event.ccAddresses
        mappedPaths.ccAddresses = true
    end
    
    -- Set status information based on threat status or quarantine
    if event.threatStatus then
        result.status = event.threatStatus
        if event.threatStatus == "active" or event.threatStatus == "detected" then
            result.status_id = 1 -- Success (threat detected)
        else
            result.status_id = 0 -- Unknown
        end
    elseif event.quarantineFolder or event.quarantineRule then
        result.status = "quarantined"
        result.status_id = 1 -- Success (quarantined)
        mappedPaths.quarantineFolder = true
        mappedPaths.quarantineRule = true
    else
        result.status_id = 0 -- Unknown
    end
    
    -- Copy unmapped fields to preserve all data
    copyUnmappedFields(event, mappedPaths, result)
    
    return result
end