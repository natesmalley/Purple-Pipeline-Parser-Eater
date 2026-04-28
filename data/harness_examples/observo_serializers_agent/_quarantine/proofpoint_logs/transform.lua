-- Proofpoint Logs to OCSF Network Activity Transformation
-- Maps Proofpoint email security events to OCSF Network Activity schema

-- OCSF Constants
local CLASS_UID = 4001
local CATEGORY_UID = 4
local CLASS_NAME = "Network Activity"
local CATEGORY_NAME = "Network Activity"

-- Helper Functions (production-proven)
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

-- Convert timestamp to milliseconds since epoch
local function parseTimestamp(timeStr)
    if not timeStr or timeStr == "" then return nil end
    
    -- Try ISO format: YYYY-MM-DDTHH:MM:SS
    local year, month, day, hour, min, sec = timeStr:match("(%d%d%d%d)-(%d%d)-(%d%d)T(%d%d):(%d%d):(%d%d)")
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
    
    -- Try epoch seconds
    local epochSec = tonumber(timeStr)
    if epochSec and epochSec > 0 then
        -- If it looks like seconds (not milliseconds), convert
        if epochSec < 9999999999 then  -- Before year 2286
            return epochSec * 1000
        else
            return epochSec
        end
    end
    
    return nil
end

-- Determine activity based on event characteristics
local function getActivity(event)
    -- Check for threat-related activity
    if event.threatID or event.threatURL or event.threatStatus then
        return {id = 6, name = "Traffic"} -- Network traffic with threat indicators
    end
    
    -- Check for email click activity
    if event.clickIP or event.clickTime then
        return {id = 5, name = "Connect"} -- User connection/click event
    end
    
    -- Default to general traffic
    return {id = 6, name = "Traffic"}
end

-- Determine severity based on threat scores and status
local function getSeverityId(event)
    -- Check threat status first
    if event.threatStatus then
        local status = string.lower(tostring(event.threatStatus))
        if status == "active" or status == "malicious" then
            return 4 -- High
        elseif status == "cleared" or status == "safe" then
            return 1 -- Informational
        end
    end
    
    -- Check various scores
    local spamScore = tonumber(event.spamScore) or 0
    local phishScore = tonumber(event.phishScore) or 0
    local malwareScore = tonumber(event.malwareScore) or 0
    local impostorScore = tonumber(event.impostorScore) or 0
    
    -- Determine highest risk score
    local maxScore = math.max(spamScore, phishScore, malwareScore, impostorScore)
    
    if maxScore >= 80 then
        return 5 -- Critical
    elseif maxScore >= 60 then
        return 4 -- High
    elseif maxScore >= 40 then
        return 3 -- Medium
    elseif maxScore >= 20 then
        return 2 -- Low
    elseif maxScore > 0 then
        return 1 -- Informational
    end
    
    return 0 -- Unknown
end

-- Main transformation function
function processEvent(event)
    if type(event) ~= "table" then return nil end
    
    local result = {}
    local mappedPaths = {}
    
    -- Field mappings using table-driven approach
    local fieldMappings = {
        -- OCSF required fields
        {type = "computed", target = "class_uid", value = CLASS_UID},
        {type = "computed", target = "category_uid", value = CATEGORY_UID},
        {type = "computed", target = "class_name", value = CLASS_NAME},
        {type = "computed", target = "category_name", value = CATEGORY_NAME},
        
        -- Network endpoints
        {type = "direct", source = "senderIP", target = "src_endpoint.ip"},
        {type = "direct", source = "clickIP", target = "dst_endpoint.ip"},
        
        -- Actor/user information
        {type = "direct", source = "sender", target = "actor.user.email_addr"},
        {type = "direct", source = "recipient", target = "dst_endpoint.user.email_addr"},
        {type = "direct", source = "fromAddress", target = "actor.user.email_addr"},
        
        -- Message details
        {type = "direct", source = "subject", target = "metadata.labels", transform = function(v) return {"subject:" .. tostring(v)} end},
        {type = "direct", source = "messageID", target = "metadata.uid"},
        {type = "direct", source = "QID", target = "metadata.correlation_uid"},
        {type = "direct", source = "GUID", target = "metadata.log_name"},
        
        -- Threat information
        {type = "direct", source = "threatID", target = "malware.name"},
        {type = "direct", source = "threatURL", target = "url_string"},
        {type = "direct", source = "classification", target = "malware.classification"},
        
        -- Metadata
        {type = "computed", target = "metadata.product.name", value = "Proofpoint Email Protection"},
        {type = "computed", target = "metadata.product.vendor_name", value = "Proofpoint"},
        {type = "computed", target = "metadata.version", value = "1.0.0"},
        
        -- Additional fields
        {type = "direct", source = "userAgent", target = "http_request.user_agent"},
        {type = "direct", source = "url", target = "url_string"},
        {type = "direct", source = "campaignID", target = "malware.uid"},
    }
    
    -- Apply field mappings
    for _, mapping in ipairs(fieldMappings) do
        if mapping.type == "direct" then
            local value = getNestedField(event, mapping.source)
            if value ~= nil and value ~= "" then
                if mapping.transform then
                    value = mapping.transform(value)
                end
                setNestedField(result, mapping.target, value)
            end
            mappedPaths[mapping.source] = true
        elseif mapping.type == "computed" then
            setNestedField(result, mapping.target, mapping.value)
        end
    end
    
    -- Set activity and type_uid
    local activity = getActivity(event)
    result.activity_id = activity.id
    result.activity_name = activity.name
    result.type_uid = CLASS_UID * 100 + activity.id
    
    -- Set severity
    result.severity_id = getSeverityId(event)
    
    -- Set time - priority order: threatTime, clickTime, messageTime, current time
    local eventTime = event.threatTime or event.clickTime or event.messageTime
    if eventTime then
        result.time = parseTimestamp(eventTime)
    end
    if not result.time then
        result.time = os.time() * 1000
    end
    
    -- Set message based on available information
    local messageParts = {}
    if event.threatStatus then
        table.insert(messageParts, "Threat Status: " .. tostring(event.threatStatus))
    end
    if event.subject then
        table.insert(messageParts, "Subject: " .. tostring(event.subject))
    end
    if event.classification then
        table.insert(messageParts, "Classification: " .. tostring(event.classification))
    end
    if #messageParts > 0 then
        result.message = table.concat(messageParts, ", ")
    else
        result.message = "Proofpoint email security event"
    end
    
    -- Create observables for threat intelligence
    local observables = {}
    if event.senderIP then
        table.insert(observables, {
            type_id = 2,
            type = "IP Address",
            name = "src_endpoint.ip",
            value = event.senderIP
        })
    end
    if event.threatURL then
        table.insert(observables, {
            type_id = 6,
            type = "URL",
            name = "url_string",
            value = event.threatURL
        })
    end
    if event.sender then
        table.insert(observables, {
            type_id = 5,
            type = "Email Address",
            name = "actor.user.email_addr",
            value = event.sender
        })
    end
    if #observables > 0 then
        result.observables = observables
    end
    
    -- Mark additional mapped fields
    local additionalMappedFields = {
        "clickIP", "clickTime", "id", "campaignID", "classification", "messageID", 
        "recipient", "sender", "senderIP", "threatID", "threatTime", "threatURL", 
        "threatStatus", "userAgent", "url", "headerCC", "headerTo", "xmailer", 
        "headerReplyTo", "messageTime", "QID", "fromAddress", "subject", 
        "spamScore", "phishScore", "impostorScore", "malwareScore", "GUID"
    }
    for _, field in ipairs(additionalMappedFields) do
        mappedPaths[field] = true
    end
    
    -- Copy unmapped fields to preserve data
    copyUnmappedFields(event, mappedPaths, result)
    
    return result
end