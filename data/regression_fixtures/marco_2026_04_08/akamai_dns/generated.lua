local CLASS_UID = 4003
local CATEGORY_UID = 4
local ACTIVITY_ID = 99
local SEVERITY_MAP = {Critical=5, High=4, Medium=3, Low=2, Informational=1, Unknown=0}

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

-- Get severity ID based on the response code
local function getSeverityId(responseCode)
    if responseCode == nil then return 0 end
    return SEVERITY_MAP[responseCode] or 0
end

function processEvent(event)
    local status, result = pcall(function()
        if type(event) ~= "table" then return nil end

        local result = {}
        local mappedPaths = {}

        -- Set required OCSF fields
        setNestedField(result, "class_uid", CLASS_UID)
        setNestedField(result, "category_uid", CATEGORY_UID)
        setNestedField(result, "activity_id", ACTIVITY_ID)
        setNestedField(result, "class_name", "DNS Activity")
        setNestedField(result, "category_name", "Network Activity")

        -- Compute type_uid
        local type_uid = CLASS_UID * 100 + ACTIVITY_ID
        setNestedField(result, "type_uid", type_uid)

        -- Set severity_id based on responseCode
        local responseCode = getNestedField(event, "responseCode")
        local severity_id = getSeverityId(responseCode)
        setNestedField(result, "severity_id", severity_id)

        -- Time: convert ISO to ms
        local eventTime = getNestedField(event, "timestamp") or getNestedField(event, "eventTime")
        if eventTime then
            local yr, mo, dy, hr, mn, sc = eventTime:match("(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)")
            if yr then
                local okTime, ts = pcall(function()
                    return os.time({year=tonumber(yr), month=tonumber(mo), day=tonumber(dy),
                                    hour=tonumber(hr), min=tonumber(mn), sec=tonumber(sc), isdst=false})
                end)
                if okTime and ts then result.time = ts * 1000 end
            end
        end

        if not result.time then
            local okNow, nowTs = pcall(function() return os.time() end)
            result.time = ((okNow and nowTs) and nowTs or 0) * 1000
        end

        -- Set activity_name
        setNestedField(result, "activity_name", "DNS Query Activity")

        -- Map source fields to OCSF fields
        setNestedField(result, "query.hostname", getNestedField(event, "domain"))
        setNestedField(result, "query.type", getNestedField(event, "recordType"))
        setNestedField(result, "rcode", responseCode)
        setNestedField(result, "answers", getNestedField(event, "answer"))
        setNestedField(result, "src_endpoint.ip", getNestedField(event, "cliIP"))

        -- Unmapped fields
        for k, v in pairs(event) do
            if not mappedPaths[k] and k ~= "_ob" and v ~= nil and v ~= "" then
                setNestedField(result, "unmapped." .. k, v)
            end
        end

        return result
    end)

    if not status then
        event["lua_error"] = tostring(result)
        return event
    end

    return result
end
