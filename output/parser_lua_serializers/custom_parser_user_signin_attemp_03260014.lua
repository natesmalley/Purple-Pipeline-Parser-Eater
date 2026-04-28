-- OCSF constants for Network Activity class
local CLASS_UID = 4001
local CATEGORY_UID = 4

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
function parseTimestamp(timestamp)
    if not timestamp then return nil end
    local year, month, day, hour, min, sec, ms = timestamp:match("(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)%.?(%d*)")
    if year then
        local time_ms = os.time({
            year = tonumber(year),
            month = tonumber(month),
            day = tonumber(day),
            hour = tonumber(hour),
            min = tonumber(min),
            sec = tonumber(sec)
        }) * 1000
        if ms and ms ~= "" then
            time_ms = time_ms + tonumber(ms)
        end
        return time_ms
    end
    return nil
end

-- Determine activity ID based on event outcome
function getActivityId(outcome)
    if not outcome then return 99 end -- Other
    local result = getNestedField(outcome, "result")
    if result == "success" then
        return 1 -- Allow/Accept
    elseif result == "failure" then
        return 2 -- Deny/Block
    end
    return 99 -- Other
end

-- Determine severity based on outcome and authentication factors
function getSeverityId(outcome, authentication)
    if not outcome then return 0 end -- Unknown
    
    local result = getNestedField(outcome, "result")
    local reason = getNestedField(outcome, "reason")
    local mfa_required = getNestedField(authentication, "mfa_required")
    local mfa_performed = getNestedField(authentication, "mfa_performed")
    
    if result == "success" then
        return 1 -- Informational
    elseif result == "failure" then
        -- Failed login with MFA bypass attempt is higher severity
        if mfa_required and not mfa_performed then
            return 4 -- High
        elseif reason == "invalid_password" or reason == "invalid_credentials" then
            return 3 -- Medium
        else
            return 2 -- Low
        end
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
        -- Required OCSF fields
        {type = "computed", target = "class_uid", value = CLASS_UID},
        {type = "computed", target = "category_uid", value = CATEGORY_UID},
        {type = "computed", target = "class_name", value = "Network Activity"},
        {type = "computed", target = "category_name", value = "Network Activity"},
        
        -- Source endpoint from client data
        {type = "direct", source = "client.ip_address", target = "src_endpoint.ip"},
        
        -- Actor information
        {type = "direct", source = "actor.name", target = "actor.user.name"},
        {type = "direct", source = "actor.email", target = "actor.user.email_addr"},
        {type = "direct", source = "actor.uuid", target = "actor.user.uid"},
        
        -- Target/destination information
        {type = "direct", source = "target.name", target = "dst_endpoint.hostname"},
        
        -- Authentication details
        {type = "direct", source = "authentication.method", target = "auth_protocol"},
        
        -- Client information
        {type = "direct", source = "client.user_agent", target = "http_request.user_agent"},
        
        -- Location information
        {type = "direct", source = "client.location.city", target = "src_endpoint.location.city"},
        {type = "direct", source = "client.location.region", target = "src_endpoint.location.region"},
        {type = "direct", source = "client.location.country", target = "src_endpoint.location.country"},
        
        -- Outcome information
        {type = "direct", source = "outcome.reason", target = "status_detail"},
    }
    
    -- Apply field mappings
    for _, mapping in ipairs(fieldMappings) do
        if mapping.type == "direct" then
            local value = getNestedField(event, mapping.source)
            if value ~= nil then
                setNestedField(result, mapping.target, value)
                -- Mark source path as mapped
                local topLevelKey = mapping.source:match("^([^.]+)")
                if topLevelKey then mappedPaths[topLevelKey] = true end
            end
        elseif mapping.type == "computed" then
            setNestedField(result, mapping.target, mapping.value)
        end
    end
    
    -- Set timestamp
    local timestamp = getNestedField(event, "timestamp")
    if timestamp then
        local parsed_time = parseTimestamp(timestamp)
        if parsed_time then
            result.time = parsed_time
        end
        mappedPaths["timestamp"] = true
    end
    
    -- Set activity_id based on outcome
    local outcome = getNestedField(event, "outcome")
    local activity_id = getActivityId(outcome)
    result.activity_id = activity_id
    result.type_uid = CLASS_UID * 100 + activity_id
    mappedPaths["outcome"] = true
    
    -- Set severity_id based on outcome and authentication context
    local authentication = getNestedField(event, "authentication")
    result.severity_id = getSeverityId(outcome, authentication)
    mappedPaths["authentication"] = true
    
    -- Set activity_name based on event type and outcome
    local event_type = getNestedField(event, "event_type")
    local outcome_result = getNestedField(outcome, "result")
    if event_type and outcome_result then
        result.activity_name = "User Sign-in " .. (outcome_result == "success" and "Success" or "Failure")
    elseif event_type then
        result.activity_name = "User Sign-in Attempt"
    else
        result.activity_name = "Network Activity"
    end
    mappedPaths["event_type"] = true
    
    -- Set status based on outcome
    if outcome_result then
        if outcome_result == "success" then
            result.status = "Success"
            result.status_id = 1
        else
            result.status = "Failure"
            result.status_id = 2
        end
    end
    
    -- Set default time if not present
    if not result.time then
        result.time = os.time() * 1000
    end
    
    -- Set metadata for unknown vendor/product
    setNestedField(result, "metadata.product.name", "Custom User Authentication System")
    setNestedField(result, "metadata.product.vendor_name", "Unknown")
    setNestedField(result, "metadata.version", "1.0.0")
    
    -- Copy unmapped fields to preserve original data
    copyUnmappedFields(event, mappedPaths, result)
    
    -- Clean empty nested tables
    local function cleanEmptyTables(tbl)
        if type(tbl) ~= "table" then return tbl end
        local isEmpty = true
        for k, v in pairs(tbl) do
            local cleaned = cleanEmptyTables(v)
            if cleaned == nil then
                tbl[k] = nil
            else
                tbl[k] = cleaned
                isEmpty = false
            end
        end
        return isEmpty and nil or tbl
    end
    
    result = cleanEmptyTables(result) or {}
    
    return result
end