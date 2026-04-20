local FEATURES = {
    FLATTEN_EVENT_TYPE = true,
}

-- Cisco Duo to OCSF Mapping Script
local OCSF_VERSION = "1.0.0"
local VENDOR = "Cisco"
local PRODUCT = "Cisco Duo"
local CATEGORY_SECURITY = "security"
local CATEGORY_IAM = "Identity & Access Management"
local CATEGORY_APP = "Application Activity"

-- Authentication Event Mappings
local authenticationMappings = {
    -- OCSF structure fields (first)
    {type="computed", value=1, target="activity_id"},
    {type="computed", value="Logon", target="activity_name"},
    {type="computed", value=3, target="category_uid"},
    {type="computed", value=CATEGORY_IAM, target="category_name"},
    {type="computed", value=3002, target="class_uid"},
    {type="computed", value="Authentication", target="class_name"},
    {type="computed", value=300201, target="type_uid"},
    {type="computed", value="Authentication: Logon", target="type_name"},
    {type="computed", value="Logon", target="event.type"},
    {type="computed", value="True", target="is_mfa"},
    {type="computed", value=VENDOR, target="metadata.product.vendor_name"},
    {type="computed", value=VENDOR, target="metadata.product.name"},
    {type="computed", value=OCSF_VERSION, target="metadata.version"},
    {type="computed", value=CATEGORY_SECURITY, target="dataSource.category"},
    {type="computed", value=PRODUCT, target="dataSource.name"},
    {type="computed", value=VENDOR, target="dataSource.vendor"},
    {type="computed", value=OCSF_VERSION, target="OCSF_version"},
    
    -- Direct field mappings (ordered to match expected output)
    {type="direct", source="isotimestamp", target="time"},
    {type="direct", source="timestamp", target="metadata.original_time"},
    {type="direct", source="access_device.hostname", target="dst_endpoint.hostname"},
    {type="direct", source="access_device.ip", target="dst_endpoint.ip"},
    {type="direct", source="access_device.location.city", target="dst_endpoint.location.city"},
    {type="direct", source="access_device.location.country", target="dst_endpoint.location.country"},
    {type="direct", source="application.key", target="service.uid"},
    {type="direct", source="application.name", target="service.name"},
    {type="direct", source="txid", target="session.uid"},
    {type="direct", source="auth_device.ip", target="src_endpoint.ip"},
    {type="direct", source="auth_device.key", target="src_endpoint.uid"},
    {type="direct", source="auth_device.location.city", target="src_endpoint.location.city"},
    {type="direct", source="auth_device.location.country", target="src_endpoint.location.country"},
    {type="direct", source="auth_device.name", target="src_endpoint.name"},
    {type="direct", source="result", target="status"},
    {type="direct", source="reason", target="status_detail"},
    {type="direct", source="user.key", target="user.uid"},
    {type="direct", source="user.name", target="user.name"},
    {type="direct", source="user.groups", target="user.groups.name"},
    {type="direct", source="email", target="user.email_addr"},
    
    -- Observables
    {type="observable", source="access_device.hostname", type_id=1, observable_type="Hostname", name="dst_endpoint.hostname"},
    {type="observable", source="access_device.ip", type_id=2, observable_type="IP Address", name="src_endpoint.ip"},
    {type="observable", source="user.name", type_id=4, observable_type="User Name", name="user.name"},
    {type="observable", source="email", type_id=5, observable_type="Email Address", name="user.email_addr"},
    {type="observable", source="application.name", type_id=9, observable_type="Process Name", name="service.name"},
    
}

-- Administrator Event Mappings
local administratorMappings = {
    -- OCSF structure fields (first)
    {type="computed", value=VENDOR, target="metadata.product.vendor_name"},
    {type="computed", value=VENDOR, target="metadata.product.name"},
    {type="computed", value=OCSF_VERSION, target="metadata.version"},
    {type="computed", value=CATEGORY_SECURITY, target="dataSource.category"},
    {type="computed", value=PRODUCT, target="dataSource.name"},
    {type="computed", value=VENDOR, target="dataSource.vendor"},
    {type="computed", value=OCSF_VERSION, target="OCSF_version"},
    
    -- Direct field mappings (ordered to match expected output)
    {type="direct", source="username", target="actor.user.name"},
    {type="direct", source="host", target="device.hostname"},
    {type="direct", source="isotimestamp", target="time"},
    {type="direct", source="timestamp", target="metadata.original_time"},
    {type="direct", source="object", target="user.name"},
    
    -- Observables
    {type="observable", source="host", type_id=1, observable_type="Hostname", name="dst_endpoint.hostname"},
    {type="observable", source="username", type_id=4, observable_type="User Name", name="actor.user.name"},
    
}

-- Telephony Event Mappings
local telephonyMappings = {
    -- OCSF structure fields (first)
    {type="computed", value=VENDOR, target="metadata.product.vendor_name"},
    {type="computed", value=VENDOR, target="metadata.product.name"},
    {type="computed", value=OCSF_VERSION, target="metadata.version"},
    {type="computed", value=CATEGORY_SECURITY, target="dataSource.category"},
    {type="computed", value=PRODUCT, target="dataSource.name"},
    {type="computed", value=VENDOR, target="dataSource.vendor"},
    {type="computed", value=OCSF_VERSION, target="OCSF_version"},
    
    -- Direct field mappings (ordered to match expected output)
    {type="direct", source="txid", target="actor.session.uid"},
    
}

-- Common field mappings for all events (ordered to match expected output)
local commonMappings = {
    {type="direct", source="event.type", target="event.type"},
    {type="direct", source="category_name", target="category_name"},
    {type="direct", source="category_uid", target="category_uid"},
    {type="direct", source="class_uid", target="class_uid"},
    {type="direct", source="activity_name", target="activity_name"},
    {type="direct", source="activity_id", target="activity_id"},
    {type="direct", source="type_uid", target="type_uid"},
    {type="direct", source="OCSF_version", target="metadata.version"},
    {type="direct", source="observables", target="observables"},
    {type="direct", source="dataSource.category", target="dataSource.category"},
    {type="direct", source="site.id", target="site.id"},
    {type="direct", source="dataSource.name", target="dataSource.name"},
    {type="direct", source="dataSource.vendor", target="dataSource.vendor"},
    {type="direct", source="message", target="message"},
    {type="direct", source="class_name", target="class_name"},
    {type="direct", source="type_name", target="type_name"},
    {type="direct", source="user.type_id", target="user.type_id"},
    {type="direct", source="isotimestamp", target="time"},
    {type="direct", source="timestamp", target="metadata.original_time"},
    {type="direct", source="object", target="user.name"},
    {type="direct", source="username", target="actor.user.name"}
}
local IGNORE_FIELDS = { _duo_event_type = true, _duo_query_time = true, _ts = true, _ob = true }

-- Helper function to combine mappings
local function combineMappings(common, specific)
    local combined = {}
    for _, mapping in ipairs(common) do
        table.insert(combined, mapping)
    end
    for _, mapping in ipairs(specific) do
        table.insert(combined, mapping)
    end
    return combined
end

-- Event type specific mappings
local eventTypeMappings = {
    ["authentication.authentication"] = {
        mappings = combineMappings(commonMappings, authenticationMappings),
        activity_id = 1, activity_name = "Logon", category_uid = 3, category_name = CATEGORY_IAM,
        class_uid = 3002, class_name = "Authentication", type_uid = 300201, 
        type_name = "Authentication: Logon", event_type = "Logon", is_mfa = "True"
    },
    ["administrator.admin_create"] = {
        mappings = combineMappings(commonMappings, administratorMappings),
        activity_id = 1, activity_name = "Create", category_uid = 3, category_name = CATEGORY_IAM,
        class_uid = 3001, class_name = "Account Change", type_uid = 300101,
        type_name = "Account Change: Create", event_type = "Create", user_type_id = 2, status_id = 99
    },
    ["administrator.admin_login"] = {
        mappings = combineMappings(commonMappings, administratorMappings),
        activity_id = 1, activity_name = "Logon", category_uid = 3, category_name = CATEGORY_IAM,
        class_uid = 3002, class_name = "Authentication", type_uid = 300202,
        type_name = "Authentication: Logon", event_type = "Logon", user_type_id = 2
    },
    ["administrator.admin_reset_password"] = {
        mappings = combineMappings(commonMappings, administratorMappings),
        activity_id = 4, activity_name = "Password Reset", category_uid = 3, category_name = CATEGORY_IAM,
        class_uid = 3001, class_name = "Account Change", type_uid = 300104,
        type_name = "Account Change: Password Reset", event_type = "Password Reset", user_type_id = 2
    },
    ["administrator.admin_update"] = {
        mappings = combineMappings(commonMappings, administratorMappings),
        activity_id = 3, activity_name = "Update", category_uid = 3, category_name = CATEGORY_IAM,
        class_uid = 3004, class_name = "Entity Management", type_uid = 300403,
        type_name = "Entity Management: Update", event_type = "Update", cloud_provider = "Cisco"
    },
    ["administrator.group_create"] = {
        mappings = combineMappings(commonMappings, administratorMappings),
        activity_id = 1, activity_name = "Create", category_uid = 3, category_name = CATEGORY_IAM,
        class_uid = 3004, class_name = "Entity Management", type_uid = 300401,
        type_name = "Entity Management: Create", event_type = "Create", cloud_provider = "Cisco"
    },
    ["administrator.group_delete"] = {
        mappings = combineMappings(commonMappings, administratorMappings),
        activity_id = 4, activity_name = "Delete", category_uid = 3, category_name = CATEGORY_IAM,
        class_uid = 3004, class_name = "Entity Management", type_uid = 300404,
        type_name = "Entity Management: Delete", event_type = "Delete", cloud_provider = "Cisco"
    },
    ["administrator.group_update"] = {
        mappings = combineMappings(commonMappings, administratorMappings),
        activity_id = 3, activity_name = "Update", category_uid = 3, category_name = CATEGORY_IAM,
        class_uid = 3004, class_name = "Entity Management", type_uid = 300403,
        type_name = "Entity Management: Update", event_type = "Update", cloud_provider = "Cisco"
    },
    ["administrator.user_create"] = {
        mappings = combineMappings(commonMappings, administratorMappings),
        activity_id = 1, activity_name = "Create", category_uid = 3, category_name = CATEGORY_IAM,
        class_uid = 3001, class_name = "Account Change", type_uid = 300101,
        type_name = "Account Change: Create", event_type = "Create", user_type_id = 2
    },
    ["administrator.user_delete"] = {
        mappings = combineMappings(commonMappings, administratorMappings),
        activity_id = 6, activity_name = "Delete", category_uid = 3, category_name = CATEGORY_IAM,
        class_uid = 3001, class_name = "Account Change", type_uid = 300106,
        type_name = "Account Change: Delete", event_type = "Delete", user_type_id = 2
    },
    ["administrator.user_update"] = {
        mappings = combineMappings(commonMappings, administratorMappings),
        activity_id = 3, activity_name = "Update", category_uid = 3, category_name = CATEGORY_IAM,
        class_uid = 3004, class_name = "Entity Management", type_uid = 300403,
        type_name = "Entity Management: Update", event_type = "Update", cloud_provider = "Cisco"
    },
    ["administrator.activation_set_password"] = {
        mappings = combineMappings(commonMappings, administratorMappings),
        activity_id = 2, activity_name = "Enable", category_uid = 3, category_name = CATEGORY_IAM,
        class_uid = 3001, class_name = "Account Change", type_uid = 300101,
        type_name = "Account Change: Enable", event_type = "Enable", user_type_id = 2
    },
    ["administrator.admin_login_error"] = {
        mappings = combineMappings(commonMappings, administratorMappings),
        activity_id = 1, activity_name = "Logon", category_uid = 3, category_name = CATEGORY_IAM,
        class_uid = 3002, class_name = "Authentication", type_uid = 300202,
        type_name = "Authentication: Logon", event_type = "Logon", user_type_id = 2
    },
    ["administrator.admin_lockout"] = {
        mappings = combineMappings(commonMappings, administratorMappings),
        activity_id = 9, activity_name = "Lock", category_uid = 3, category_name = CATEGORY_IAM,
        class_uid = 3001, class_name = "Account Change", type_uid = 300109,
        type_name = "Account Change: Lock", event_type = "Lock", user_type_id = 2
    },
    ["telephony.enrollment"] = {
        mappings = combineMappings(commonMappings, telephonyMappings),
        activity_id = 1, activity_name = "Create", category_uid = 3, category_name = CATEGORY_IAM,
        class_uid = 3001, class_name = "Account Change", type_uid = 300201,
        type_name = "Account Change: Create", event_type = "Create"
    },
    ["telephony.authentication"] = {
        mappings = combineMappings(commonMappings, telephonyMappings),
        activity_id = 1, activity_name = "Logon", category_uid = 3, category_name = CATEGORY_IAM,
        class_uid = 3002, class_name = "Authentication", type_uid = 300201,
        type_name = "Authentication: Logon", event_type = "Logon"
    },
    ["telephony.administrator login"] = {
        mappings = combineMappings(commonMappings, telephonyMappings),
        activity_id = 1, activity_name = "Logon", category_uid = 3, category_name = CATEGORY_IAM,
        class_uid = 3002, class_name = "Authentication", type_uid = 300201,
        type_name = "Authentication: Logon", event_type = "Logon"
    },
    ["unknown.unknown"] = {
        mappings = commonMappings,
        activity_id = 99, activity_name = "Other", category_uid = 6, category_name = CATEGORY_APP,
        class_uid = 6003, class_name = "API Activity", type_uid = 600399,
        type_name = "API Activity: Other", event_type = "Other"
    }
}

function getNestedField(obj, path)
    if not obj or not path or path == '' then return nil end
    local current = obj
    for key in string.gmatch(path, '[^.]+') do
        if not current or not key then return nil end
        current = current[key]
    end
    return current
end

function setNestedField(obj, path, value)
    if not value or not path or path == '' then return end
    local keys = {}
    for key in string.gmatch(path, '[^.]+') do
        table.insert(keys, key)
    end
    local current = obj
    for i = 1, #keys - 1 do
        if not current[keys[i]] then current[keys[i]] = {} end
        current = current[keys[i]]
    end
    current[keys[#keys]] = value
end

function json_encode(obj, key)
    if obj == nil then return "null" end
    if type(obj) == "boolean" or type(obj) == "number" then return tostring(obj) end
    if type(obj) == "string" then return '"' .. obj:gsub('"', '\\"') .. '"' end
    if type(obj) == "table" then
        local isArray = true
        local maxIndex = 0
        for k, v in pairs(obj) do
            if type(k) ~= "number" then isArray = false; break end
            maxIndex = math.max(maxIndex, k)
        end
        
        if isArray then
            if maxIndex > 0 then
            local items = {}
            for i = 1, maxIndex do
                    if obj[i] ~= nil then
                        table.insert(items, json_encode(obj[i], key))
                    else
                        table.insert(items, "null")
                    end
                end
                return "[" .. table.concat(items, ", ") .. "]"
            else
                return "[]"
            end
        else
            local items = {}
            for k, v in pairs(obj) do
                    local keyStr = type(k) == "string" and k or tostring(k)
                    table.insert(items, '"' .. keyStr:gsub('"', '\\"') .. '": ' .. json_encode(v, keyStr))
            end
            return "{" .. table.concat(items, ", ") .. "}"
        end
    end
    return '"' .. tostring(obj) .. '"'
end

-- Field ordering maps for consistent JSON serialization (preorder traversal)
local FIELD_ORDERS = {
    access_device = {
        "hostname", "browser_version", "browser", "security_agents", "os_version", 
        "is_password_set", "java_version", "os", "location", "is_firewall_enabled", 
        "ip", "flash_version", "is_encryption_enabled"
    },
    location = {
        "city", "state", "country"
    },
    adaptive_trust_assessments = {
        "more_secure_auth", "remember_me"
    },
    more_secure_auth = {
        "features_version", "model_version", "policy_enabled", "trust_level", "reason"
    },
    remember_me = {
        "features_version", "model_version", "policy_enabled", "trust_level", "reason"
    },
    application = {
        "name", "key"
    },
    auth_device = {
        "name", "ip", "location", "key"
    },
    user = {
        "key", "name", "groups"
    },
    message = {
        "access_device", "adaptive_trust_assessments", "alias", "application", 
        "auth_device", "email", "event_type", "factor", "isotimestamp", 
        "ood_software", "reason", "result", "timestamp", "trusted_endpoint_status", 
        "txid", "user", "site"
    },
    admin_message = {
        "action", "description", "isotimestamp", "object", "timestamp", 
        "username", "eventtype", "host", "site"
    },
    -- Unified message field order for all event types (admin/auth/telephony)
    message_all = {
        -- Administrator-style fields first
        "action", "description", "isotimestamp", "object", "timestamp",
        "username", "eventtype", "host", "site",
        -- Authentication/telephony-style fields afterwards
        "access_device", "adaptive_trust_assessments", "alias", "application",
        "auth_device", "email", "event_type", "factor",
        "ood_software", "reason", "result", "trusted_endpoint_status",
        -- Ensure deterministic ordering for common telephony fields
        "txid", "phone", "credits", "ts", "context", "telephony_id", "type",
        "user"
    }
}

-- Helper function to encode objects with specific field order (preorder traversal)
function encodeWithFieldOrder(obj, fieldOrder)
    local items = {}
    -- Phase 1: Process fields in predefined order
    for _, fieldName in ipairs(fieldOrder) do
        if obj[fieldName] ~= nil then
            local valueStr = json_encode_ordered(obj[fieldName], fieldName)
            table.insert(items, '"' .. fieldName .. '": ' .. valueStr)
        end
    end
    -- Phase 2: Process remaining fields not in the order list
    for k, v in pairs(obj) do
        local found = false
        for _, fieldName in ipairs(fieldOrder) do
            if k == fieldName then found = true; break end
        end
        if not found then
            local valueStr = json_encode_ordered(v, k)
            table.insert(items, '"' .. k .. '": ' .. valueStr)
        end
    end
    return "{" .. table.concat(items, ", ") .. "}"
end

function json_encode_ordered(obj, key)
    if obj == nil then return "null" end
    if type(obj) == "boolean" or type(obj) == "number" then return tostring(obj) end
    if type(obj) == "string" then return '"' .. obj:gsub('"', '\\"') .. '"' end
    if type(obj) == "table" then
        local isArray = true
        local maxIndex = 0
        for k, v in pairs(obj) do
            if type(k) ~= "number" then isArray = false; break end
            maxIndex = math.max(maxIndex, k)
        end
        
        if isArray then
            if maxIndex > 0 then
                local items = {}
                for i = 1, maxIndex do
                    if obj[i] ~= nil then
                        table.insert(items, json_encode_ordered(obj[i], key))
                    else
                        table.insert(items, "null")
                    end
                end
                return "[" .. table.concat(items, ", ") .. "]"
            else
                return "[]"
            end
        else
            -- Use field order maps for known object types (preorder traversal)
            if key and FIELD_ORDERS[key] then
                return encodeWithFieldOrder(obj, FIELD_ORDERS[key])
            else
                -- For unknown objects, use alphabetical ordering for consistency
                local items = {}
                local orderedKeys = {}
                for k, v in pairs(obj) do
                    if type(k) == "number" then
                        table.insert(orderedKeys, {k, v, true})
                    end
                end
                table.sort(orderedKeys, function(a, b) return a[1] < b[1] end)
                
                for k, v in pairs(obj) do
                    if type(k) == "string" then
                        table.insert(orderedKeys, {k, v, false})
                    end
                end
                
                for _, item in ipairs(orderedKeys) do
                    local k, v, isNumeric = item[1], item[2], item[3]
                    local keyStr = isNumeric and tostring(k) or '"' .. k:gsub('"', '\\"') .. '"'
                    table.insert(items, keyStr .. ': ' .. json_encode_ordered(v, k))
                end
                return "{" .. table.concat(items, ", ") .. "}"
            end
        end
    end
    return '"' .. tostring(obj) .. '"'
end

json = { encode = json_encode }

function findEventType(log)
    if getNestedField(log, 'event_type') then
        return 'authentication.' .. string.lower(getNestedField(log, 'event_type'))
    elseif getNestedField(log, 'context') then
        return 'telephony.' .. string.lower(getNestedField(log, 'context'))
    elseif getNestedField(log, 'eventtype') then
        local action = getNestedField(log, 'action') or 'unknown'
        return 'administrator.' .. string.lower(action)
    end
    return 'unknown.unknown'
end

function buildObservablesFromMappings(event, mappings)
    local observables = {}
    
    for _, mapping in ipairs(mappings) do
        if mapping.type == "observable" then
            local value = getNestedField(event, mapping.source)
            if value and value ~= "-" then
            table.insert(observables, {
                    type_id = mapping.type_id,
                    type = mapping.observable_type,
                    name = mapping.name,
                    value = value
            })
        end
        end
    end
    
    return observables
end

function iso8601_to_epoch_ms(timestr)
    -- Try to parse with fractional seconds
    local year, month, day, hour, min, sec, frac, offset_sign, offset_hour, offset_min =
        timestr:match("^(%d+)%-(%d+)%-(%d+)T(%d+):(%d+):(%d+)%.(%d+)([+-])(%d+):(%d+)$")

    -- If fractional seconds not present, try without fraction
    if not year then
        year, month, day, hour, min, sec, offset_sign, offset_hour, offset_min =
            timestr:match("^(%d+)%-(%d+)%-(%d+)T(%d+):(%d+):(%d+)([+-])(%d+):(%d+)$")
        frac = "0"
    end

    -- Handle Z (UTC) format
    if not year then
        year, month, day, hour, min, sec, frac = timestr:match("^(%d+)%-(%d+)%-(%d+)T(%d+):(%d+):(%d+)%.?(%d*)Z$")
        offset_sign, offset_hour, offset_min = "+", "0", "0"
        if frac == "" then frac = "0" end
    end

    -- Convert to numeric
    year, month, day, hour, min, sec = tonumber(year), tonumber(month), tonumber(day),
                                       tonumber(hour), tonumber(min), tonumber(sec)
    offset_hour, offset_min = tonumber(offset_hour), tonumber(offset_min)
    local frac_ms = tonumber(frac:sub(1,3))  -- take first 3 digits as milliseconds

    -- Convert to UTC timestamp
    local utc_time = os.time({
        year = year,
        month = month,
        day = day,
        hour = hour,
        min = min,
        sec = sec
    })

    -- Adjust for timezone offset
    local offset_seconds = offset_hour * 3600 + offset_min * 60
    if offset_sign == "+" then
        utc_time = utc_time - offset_seconds
    else
        utc_time = utc_time + offset_seconds
    end

    -- Return epoch milliseconds
    return utc_time * 1000 + frac_ms
end

-- Apply mappings and add unmapped fields with "unmapped." prefix
function getParsedEvent(event, mappings)
    local result = {}
    local mappedFields = {}

    -- Apply field mappings first
    for _, mapping in ipairs(mappings) do
        local value = nil

        if mapping.type == "computed" then
            value = mapping.value
        elseif mapping.type == "direct" then
            value = getNestedField(event, mapping.source)
        elseif mapping.type == "observable" then
            -- Observables handled elsewhere
        end

        if mapping.type == "direct" or mapping.type == "computed" then
            -- Skip fields with value "-"
            if value ~= "-" then
                setNestedField(result, mapping.target, value)
                mappedFields[mapping.target] = true
                -- Also mark source field as mapped to prevent it from going to unmapped
                if mapping.type == "direct" then
                    mappedFields[mapping.source] = true
                end
            end
        end
    end
    
    -- Special handling for cloud.provider field (can't use getNestedField due to dot in field name)
    if event['cloud.provider'] and event['cloud.provider'] ~= "-" then
        result['cloud.provider'] = event['cloud.provider']
        mappedFields['cloud.provider'] = true
    end
    
    -- Special handling for dataSource object (set in processEvent, should not go to unmapped)
    if event['dataSource'] and type(event['dataSource']) == 'table' then
        result['dataSource'] = event['dataSource']
        mappedFields['dataSource'] = true
        -- Also mark individual dataSource fields as mapped
        if event['dataSource'].category then
            mappedFields['dataSource.category'] = true
        end
        if event['dataSource'].name then
            mappedFields['dataSource.name'] = true
        end
        if event['dataSource'].vendor then
            mappedFields['dataSource.vendor'] = true
        end
    end
    
    -- Special handling for event object (set in processEvent, should not go to unmapped)
    if event['event'] and type(event['event']) == 'table' then
        result['event'] = event['event']
        mappedFields['event'] = true
        -- Also mark individual event fields as mapped
        if event['event'].type then
            mappedFields['event.type'] = true
        end
    end
    
    -- Special handling for synthetic fields set in processEvent (should not go to unmapped)
    local syntheticFields = {
        'activity_id', 'activity_name', 'category_uid', 'category_name', 
        'class_uid', 'class_name', 'type_uid', 'type_name',
        'OCSF_version', 'user'
    }
    for _, field in ipairs(syntheticFields) do
        if event[field] then
            -- If both result and event values are tables, merge without overwriting existing keys
            if type(event[field]) == 'table' and type(result[field]) == 'table' then
                for k, v in pairs(event[field]) do
                    if result[field][k] == nil then
                        result[field][k] = v
                    end
                end
            else
                result[field] = event[field]
            end
            mappedFields[field] = true
        end
    end

    -- Copy remaining unmapped fields with prefix
    for key, value in pairs(event) do
        if not IGNORE_FIELDS[key] and not mappedFields[key] then
            -- Skip fields with value "-"
            if value ~= "-" then
                if type(value) == 'table' then
                    local nestedObj = {}
                    for nestedKey, nestedValue in pairs(value) do
                        if type(nestedValue) ~= 'function' and nestedValue ~= "-" then
                            nestedObj[nestedKey] = nestedValue
                        end
                    end
                    if next(nestedObj) then
                        result["unmapped." .. key] = nestedObj
                    end
                else
                    result["unmapped." .. key] = value
                end
            end
        end
    end

    -- Convert time field to epoch milliseconds if it exists
    if result.time then
        result.time = iso8601_to_epoch_ms(result.time)
    end

    if FEATURES.FLATTEN_EVENT_TYPE then
        if result and result.event then
            result['event.type'] = result.event.type
        end
    end
    return result
end

function processEvent(event)
    if not event then return event end

    -- Set eventtype based on _duo_event_type if eventtype doesn't exist
    if getNestedField(event, '_duo_event_type') == 'administrator' and not getNestedField(event, 'eventtype') then
        event.eventtype = 'administrator'
    end

    local eventType = findEventType(event)
    local eventDef = eventTypeMappings[eventType] or eventTypeMappings["unknown.unknown"]
    
    -- Step 1: Set site.id (setSiteId equivalent)
    -- Load site ID from event data (site.id, site_id, or siteId)
    local siteId = getNestedField(event, 'site.id') or getNestedField(event, 'site_id') or getNestedField(event, 'siteId')
    if siteId then
        if not event.site then event.site = {} end
        event.site.id = siteId
    end
    


    local msg_event = {}
    for k, v in pairs(event) do
        if (not IGNORE_FIELDS[k]) then
            msg_event[k] = v
        end
    end
    event["message"] = json_encode_ordered(msg_event, 'message_all')
    
    -- Step 3: Apply synthetic fields (setciscoDuoSyntheticFields equivalent)
    if eventDef.activity_id then event.activity_id = eventDef.activity_id end
    if eventDef.activity_name then event.activity_name = eventDef.activity_name end
    if eventDef.category_uid then event.category_uid = eventDef.category_uid end
    if eventDef.category_name then event.category_name = eventDef.category_name end
    if eventDef.class_uid then event.class_uid = eventDef.class_uid end
    if eventDef.class_name then event.class_name = eventDef.class_name end
    if eventDef.type_uid then event.type_uid = eventDef.type_uid end
    if eventDef.type_name then event.type_name = eventDef.type_name end
    
    -- Set event object
    event['event'] = {type = eventDef.event_type}
    
    -- Add user object for administrator events
    if string.find(eventType, '^administrator') and eventDef.user_type_id then
        event['user'] = {type_id = eventDef.user_type_id}
    end
    
    -- Add status_id for admin_create events
    if eventDef.status_id then
        event['status_id'] = eventDef.status_id
    end
    
    if eventDef.is_mfa then
        event['is_mfa'] = eventDef.is_mfa
    end
    
    if eventDef.cloud_provider then
        event['cloud.provider'] = eventDef.cloud_provider
    end
    
    -- Set observables (from setciscoDuoSyntheticFields)
    local observables = buildObservablesFromMappings(event, eventDef.mappings)
    if #observables > 0 then 
        event.observables = observables
    end
    
    -- Set common fields (from setciscoDuoSyntheticFields end)
    event["dataSource"] = {name = "Cisco Duo", category = "security", vendor = "Cisco"}
    event["OCSF_version"] = "1.0.0"
    -- Step 4: Apply field mappings and unmapped handling (getParsedEvent parity)
    return getParsedEvent(event, eventDef.mappings)
end

function process(event, emit)
    local out = processEvent(event["log"])
    if out ~= nil then
        event["log"] = out
        emit(event)
    end
end

