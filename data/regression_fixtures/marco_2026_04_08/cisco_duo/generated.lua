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

-- Collect unmapped fields (preserves data not in field mappings)
function copyUnmappedFields(event, mappedPaths, result)
    for k, v in pairs(event) do
        if not mappedPaths[k] and k ~= "_ob" and v ~= nil and v ~= "" then
            setNestedField(result, "unmapped." .. tostring(k), v)
        end
    end
end

function processEvent(event)
    local status, err = pcall(function()
        if type(event) ~= "table" then return nil end

        local result = {}
        local mappedPaths = {}

        -- Set required OCSF fields
        local class_uid = 3002
        local category_uid = 3
        local activity_id = tonumber(getNestedField(event, "activity_id")) or 0
        local severity_id = tonumber(getNestedField(event, "severity_id")) or 0
        local timestamp = tonumber(getNestedField(event, "timestamp")) or tonumber(getNestedField(event, "time")) or 0

        -- Set OCSF fields
        setNestedField(result, "class_uid", class_uid)
        setNestedField(result, "category_uid", category_uid)
        setNestedField(result, "activity_id", activity_id)
        setNestedField(result, "type_uid", class_uid * 100 + activity_id)
        setNestedField(result, "severity_id", severity_id)
        setNestedField(result, "class_name", "Authentication")
        setNestedField(result, "category_name", "Identity & Access Management")
        setNestedField(result, "activity_name", tostring(getNestedField(event, "activity_name") or ''))

        -- Set time as milliseconds since epoch
        setNestedField(result, "time", timestamp)

        -- Map common optional fields
        setNestedField(result, "message", getNestedField(event, "message"))
        setNestedField(result, "status", getNestedField(event, "status"))
        setNestedField(result, "status_id", getNestedField(event, "status_id"))
        setNestedField(result, "src_endpoint.ip", getNestedField(event, "src_endpoint.ip"))
        setNestedField(result, "src_endpoint.hostname", getNestedField(event, "src_endpoint.hostname"))
        setNestedField(result, "src_endpoint.port", getNestedField(event, "src_endpoint.port"))

        -- Unmapped fields
        copyUnmappedFields(event, mappedPaths, result)

        return result
    end)

    if not status then
        event["lua_error"] = tostring(err)
        return event
    end

    return result
end
