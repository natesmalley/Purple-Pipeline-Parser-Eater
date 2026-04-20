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

-- Collect unmapped fields (preserves data not in field mappings)
function copyUnmappedFields(event, mappedPaths, result)
    for k, v in pairs(event) do
        if not mappedPaths[k] and k ~= "_ob" and v ~= nil and v ~= "" then
            setNestedField(result, "unmapped." .. tostring(k), v)
        end
    end
end

-- Function to determine severity_id based on ActionType
local function getSeverityId(actionType)
    if actionType == nil then return 0 end
    local severityMap = {
        NetworkConnectionFailed = 4,
        DomainBlocked = 3,
    }
    return severityMap[actionType] or 0
end

function processEvent(event)
    local status, result = pcall(function()
        if type(event) ~= "table" then return nil end

        local mappedPaths = {}
        result = {}

        -- Set required OCSF fields
        setNestedField(result, "class_uid", 2004)
        setNestedField(result, "category_uid", 2)
        setNestedField(result, "class_name", "Detection Finding")
        setNestedField(result, "category_name", "Findings")

        local actionType = getValue(event, "ActionType", "")
        local timestamp = getValue(event, "Timestamp", "")
        local findingTitle = getValue(event, "ProcessName", "Unknown Process")
        local findingUid = getValue(event, "scenario.trace_id", "Unknown UID")

        setNestedField(result, "finding_info.title", findingTitle)
        setNestedField(result, "finding_info.uid", findingUid)
        setNestedField(result, "severity_id", getSeverityId(actionType))

        local activity_id = 99
        setNestedField(result, "activity_id", activity_id)
        setNestedField(result, "type_uid", 2004 * 100 + activity_id)

        if timestamp then
            local yr, mo, dy, hr, mn, sc = timestamp:match("(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)")
            if yr then
                local okTime, ts = pcall(function()
                    return os.time({year=tonumber(yr), month=tonumber(mo), day=tonumber(dy),
                                    hour=tonumber(hr), min=tonumber(mn), sec=tonumber(sc), isdst=false})
                end)
                if okTime and ts then
                    result.time = ts * 1000
                end
            end
        end

        if not result.time then
            local okNow, nowTs = pcall(function() return os.time() end)
            result.time = ((okNow and nowTs) and nowTs or 0) * 1000
        end

        copyUnmappedFields(event, mappedPaths, result)
        return result
    end)

    if not status then
        event["lua_error"] = tostring(result)
        return event
    end

    return result
end
