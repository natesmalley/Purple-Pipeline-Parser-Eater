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

-- Convert timestamp to milliseconds since epoch
function parseTimestamp(timestamp)
    if not timestamp then return nil end
    local yr, mo, dy, hr, mn, sc, ms = timestamp:match("(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)%.?(%d*)")
    if yr then
        local time_s = os.time({
            year = tonumber(yr),
            month = tonumber(mo),
            day = tonumber(dy),
            hour = tonumber(hr),
            min = tonumber(mn),
            sec = tonumber(sc),
            isdst = false
        })
        local ms_part = ms and tonumber(ms) or 0
        if #ms == 3 then
            return time_s * 1000 + ms_part
        else
            return time_s * 1000
        end
    end
    return nil
end

-- Map severity based on event outcome and type
function getSeverityId(event)
    local outcome = getNestedField(event, 'outcome.result')
    local event_type = event.event_type
    
    if outcome == 'success' then
        return 1 -- Informational
    elseif outcome == 'failure' or outcome == 'error' then
        return 3 -- Medium
    elseif event_type and string.find(event_type, 'failure') then
        return 3 -- Medium
    elseif event_type and string.find(event_type, 'error') then
        return 4 -- High
    else
        return 0 -- Unknown
    end
end

-- Determine activity ID based on event type
function getActivityId(event_type)
    if not event_type then return 99 end -- Other
    
    if string.find(event_type, 'signin') then
        return 1 -- Connect
    elseif string.find(event_type, 'signout') or string.find(event_type, 'logout') then
        return 2 -- Disconnect
    elseif string.find(event_type, 'connect') then
        return 1 -- Connect
    elseif string.find(event_type, 'disconnect') then
        return 2 -- Disconnect
    elseif string.find(event_type, 'request') then
        return 5 -- Request
    elseif string.find(event_type, 'response') then
        return 6 -- Response
    else
        return 99 -- Other
    end
end

-- Get activity name from event type
function getActivityName(event_type)
    if not event_type then return 'Unknown' end
    
    local activity_map = {
        ['signin'] = 'User Sign-in',
        ['signout'] = 'User Sign-out',
        ['logout'] = 'User Logout',
        ['connect'] = 'Network Connect',
        ['disconnect'] = 'Network Disconnect',
        ['request'] = 'Network Request',
        ['response'] = 'Network Response'
    }
    
    for pattern, name in pairs(activity_map) do
        if string.find(event_type, pattern) then
            return name
        end
    end
    
    return 'Other'
end

-- Field mapping configuration
local fieldMappings = {
    {type = "direct", source = "timestamp", target = "raw_data"},
    {type = "direct", source = "event_type", target = "message"},
    {type = "direct", source = "client.ip_address", target = "src_endpoint.ip"},
    {type = "direct", source = "client.user_agent", target = "src_endpoint.hostname"},
    {type = "direct", source = "actor.email", target = "actor.user.name"},
    {type = "direct", source = "actor.uuid", target = "actor.user.uid"},
    {type = "direct", source = "session.uuid", target = "session.uid"},
    {type = "direct", source = "authentication.method", target = "auth_protocol"},
    {type = "computed", target = "class_uid", value = CLASS_UID},
    {type = "computed", target = "category_uid", value = CATEGORY_UID},
    {type = "computed", target = "class_name", value = CLASS_NAME},
    {type = "computed", target = "category_name", value = CATEGORY_NAME},
    {type = "computed", target = "metadata.product.name", value = "Custom Network Monitor"},
    {type = "computed", target = "metadata.product.vendor_name", value = "Unknown"},
    {type = "computed", target = "metadata.version", value = "1.0"}
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
        elseif mapping.type == "computed" then
            setNestedField(result, mapping.target, mapping.value)
        end
    end

    -- Set activity-specific fields
    local event_type = event.event_type
    local activity_id = getActivityId(event_type)
    local activity_name = getActivityName(event_type)
    local severity_id = getSeverityId(event)
    local type_uid = CLASS_UID * 100 + activity_id

    result.activity_id = activity_id
    result.type_uid = type_uid
    result.severity_id = severity_id
    result.activity_name = activity_name

    -- Handle timestamp conversion
    local timestamp = event.timestamp
    if timestamp then
        local time_ms = parseTimestamp(timestamp)
        result.time = time_ms or (os.time() * 1000)
        mappedPaths['timestamp'] = true
    else
        result.time = os.time() * 1000
    end

    -- Set status based on outcome
    local outcome = getNestedField(event, 'outcome.result')
    if outcome then
        result.status = outcome
        result.status_id = (outcome == 'success') and 1 or 2
        mappedPaths['outcome'] = true
    end

    -- Handle authentication details
    local auth_method = getNestedField(event, 'authentication.method')
    local mfa_required = getNestedField(event, 'authentication.mfa_required')
    local mfa_performed = getNestedField(event, 'authentication.mfa_performed')
    
    if auth_method or mfa_required or mfa_performed then
        mappedPaths['authentication'] = true
    end

    -- Handle client details
    local client_ip = getNestedField(event, 'client.ip_address')
    local user_agent = getNestedField(event, 'client.user_agent')
    
    if client_ip or user_agent then
        mappedPaths['client'] = true
    end

    -- Handle actor details
    local actor_email = getNestedField(event, 'actor.email')
    local actor_uuid = getNestedField(event, 'actor.uuid')
    
    if actor_email or actor_uuid then
        mappedPaths['actor'] = true
    end

    -- Handle session details
    local session_uuid = getNestedField(event, 'session.uuid')
    local session_created = getNestedField(event, 'session.created_at')
    
    if session_uuid or session_created then
        mappedPaths['session'] = true
    end

    -- Mark event_type as mapped
    if event_type then
        mappedPaths['event_type'] = true
    end

    -- Copy unmapped fields to preserve data
    copyUnmappedFields(event, mappedPaths, result)

    return result
end