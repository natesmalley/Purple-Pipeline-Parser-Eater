-- AWS Web Application Firewall OCSF 1.0.0-rc3-rc.3 Schema Serializer

local FEATURES = {
    CLEANUP_EMPTY_NULL = true,
}

local FIELD_MAPPINGS = {
    {source = "action", target = "unmapped.action"},
    {source = "captchaResponse.responseCode", target = "unmapped.captchaResponse.responseCode"},
    {source = "captchaResponse.solveTimestamp", target = "unmapped.captchaResponse.solveTimestamp"},
    {source = "captchaResponse.failureReason", target = "unmapped.captchaResponse.failureReason"},
    {source = "challengeResponse", target = "unmapped.challengeResponse"},
    {source = "excludedRules", target = "unmapped.excludedRules"},
    {source = "formatVersion", target = "metadata.log_version"},
    {source = "httpRequest.httpMethod", target = "http_request.http_method"},
    {source = "httpRequest.clientIp", target = "src_endpoint.ip"},
    {source = "httpRequest.country", target = "src_endpoint.location.country"},
    {source = "httpRequest.headers", target = "http_request.http_headers"},
    {source = "httpRequest.uri", target = "web_resources.url.path"},
    {source = "httpRequest.args", target = "http_request.args"},
    {source = "httpRequest.requestId", target = "http_request.uid"},
    {source = "httpSourceId", target = "web_resources.uid"},
    {source = "httpSourceName", target = "web_resources.name"},
    {source = "httpRequest.httpVersion", target = "http_request.version"},
    {source = "labels", target = "web_resources.labels"},
    {source = "nonTerminatingMatchingRules", target = "unmapped.nonTerminatingMatchingRules"},
    {source = "oversizeFields", target = "unmapped.oversizeFields"},
    {source = "rateBasedRuleList", target = "unmapped.rateBasedRuleList"},
    {source = "requestHeadersInserted", target = "unmapped.requestHeadersInserted"},
    {source = "responseCodeSent", target = "http_response.code"},
    {source = "ruleGroupList", target = "unmapped.ruleGroupList"},
    {source = "terminatingRuleMatchDetails", target = "unmapped.terminatingRuleMatchDetails"},
    {source = "terminatingRuleType", target = "unmapped.terminatingRuleType"},
    {source = "timestamp", target = "metadata.original_time"},
    {source = "webaclId", target = "unmapped.webaclId"},
}

local ALLOW_FIELD_ORDER = {
  message = {
    "timestamp", "formatVersion", "webaclId", "terminatingRuleId", "terminatingRuleType", "action",
    "terminatingRuleMatchDetails", "httpSourceName", "httpSourceId", "ruleGroupList", "rateBasedRuleList",
    "nonTerminatingMatchingRules", "httpRequest", "labels"
  },
  httpRequest = {
    "clientIp", "country", "headers", "uri", "args", "httpVersion", "httpMethod", "requestId"
  },
  headers = {
    "name", "value"
  },
  labels = {
    "name"
  },
  nonTerminatingMatchingRules = {
    "ruleId", "action", "ruleMatchDetails"
  },
  ruleMatchDetails = {
    "conditionType", "sensitivityLevel", "location", "matchedData"
  },
  terminatingRuleMatchDetails = {
    "conditionType", "sensitivityLevel", "location", "matchedData"
  },
  ruleGroupList = {
    "ruleGroupId", "terminatingRule", "nonTerminatingMatchingRules", "excludedRules"
  },
  rateBasedRuleList = {
    "ruleId", "action", "limitAndHandlingRuleId", "limitAndHandlingRuleType"
  },
}

local BLOCK_FIELD_ORDER = {
  message = {
    "timestamp", "formatVersion", "webaclId", "terminatingRuleId", "terminatingRuleType", "action",
    "terminatingRuleMatchDetails", "httpSourceName", "httpSourceId", "ruleGroupList", "rateBasedRuleList",
    "nonTerminatingMatchingRules", "requestHeadersInserted", "responseCodeSent", "httpRequest"
  },
  httpRequest = {
    "clientIp", "country", "headers", "uri", "args", "httpVersion", "httpMethod", "requestId"
  },
  headers = {
    "name", "value"
  },
  rateBasedRuleList = {
    "rateBasedRuleId", "rateBasedRuleName", "limitKey", "maxRateAllowed", "evaluationWindowSec", "customValues"
  },
  customValues = {
    "key", "name", "value"
  },
}

local CAPTCHA_FIELD_ORDER = {
  message = {
    "timestamp", "formatVersion", "webaclId", "terminatingRuleId", "terminatingRuleType", "action",
    "terminatingRuleMatchDetails", "httpSourceName", "httpSourceId", "ruleGroupList", "rateBasedRuleList",
    "nonTerminatingMatchingRules", "requestHeadersInserted", "responseCodeSent", "httpRequest", "captchaResponse"
  },
  httpRequest = {
    "clientIp", "country", "headers", "uri", "args", "httpVersion", "httpMethod", "requestId"
  },
  headers = {
    "name", "value"
  },
  captchaResponse = {
    "responseCode", "solveTimestamp", "failureReason"
  },
}

local function getActivityId(action) 
    if action == "block" then
        return 2
    elseif action == "allow" then
        return 1
    elseif action == "captcha" then
        return 99
    elseif action == "challenge" then
        return 99
    else
        return 0
    end
end

local function getActivityName(action) 
    if action == "block" then
        return "Access Deny"
    elseif action == "allow" then
        return "Access Grant"
    elseif action == "captcha" then
        return "CAPTCHA"    
    else
        return "Other"
    end
end

local function getTypeName(action) 
    if action == "block" then
        return "Web Resource Access Activity: Access Deny"
    elseif action == "allow" then
        return "Web Resource Access Activity: Access Grant"
    else
        return "Web Resource Access Activity: Other"
    end
end

local function getTypeUID(action) 
    if action == "block" then
        return 600402
    elseif action == "allow" then
        return 600401
    else
        return 600499
    end
end

local function safelyAccessNestedDictKeys(keys, dictObject)
    local current = dictObject
    for _, key in ipairs(keys) do
        if type(current) ~= "table" then
            return nil
        end
        current = current[key]
    end
    return current
end

local function getConstantFields(action, source) 
    local activity_id = getActivityId(action)
    local activity_name = getActivityName(action)
    local type_name = getTypeName(action)
    local type_uid = getTypeUID(action)
    local event_type = getActivityName(action)
    local ipAddress = safelyAccessNestedDictKeys({"httpRequest", "clientIp"}, source)
    local observables = {{type_id = 2, type = "IP Address", name = "src_endpoint.ip", value = ipAddress}}

    local fields = {
        ["activity_id"] = activity_id,
        ["activity_name"] = activity_name,
        ["category_uid"] = 6,
        ["category_name"] = "Application Activity",
        ["class_uid"] = 6004,
        ["class_name"] = "Web Resource Access Activity",
        ["severity_id"] = 99,
        ["metadata.version"] = "1.0.0-rc3",
        ["metadata.product.vendor_name"] = "AWS",
        ["metadata.product.name"] = "AWS Web Application Firewall",
        ["type_name"] = type_name,
        ["type_uid"] = type_uid,
        ["event.type"] = event_type,
        ["dataSource.vendor"] = "AWS",
        ["dataSource.name"] = "AWS Web Application Firewall",
        ["dataSource.category"] = "security",
        ["observables"] = observables,
        ["status_id"] = 99,
        ["status"] = "Other",
        ["cloud.provider"] = "AWS",
    }
    
    return fields
end

local IGNORE_KEYS = {
    _ob = true,
}


-- Utility functions
local function split(str, delimiter)
    if not str or str == "" then
        return {}
    end
    local result = {}
    for token in string.gmatch(str, "([^" .. delimiter .. "]+)") do
        table.insert(result, token)
    end
    return result
end
local function getValueByPath(obj, path)
    local current = obj
    for _, part in ipairs(split(path, ".")) do
        if type(current) ~= "table" then
            return nil
        end
        local key = tonumber(part) or part
        current = current[key]
    end
    return current
end
local function setValueByPath(obj, path, value)
    local parts = split(path, ".")
    local current = obj
    for i = 1, #parts - 1 do
        local key = tonumber(parts[i]) or parts[i]
        if current[key] == nil or type(current[key]) ~= "table" then
            current[key] = {}
        end
        current = current[key]
    end
    local last = parts[#parts]
    if value == nil then
        current[last] = nil
    else
        current[last] = value
    end
end

local function deepCopy(value, ignoreKeys)
    if type(value) ~= "table" then
        return value
    end
    local copy = {}
    for k, v in pairs(value) do
        if not (ignoreKeys and ignoreKeys[k]) then
            copy[k] = deepCopy(v, ignoreKeys)
        end
    end
    return copy
end

-- Helper: Encode Lua table to JSON string with field ordering
local function encodeJson(obj, fieldOrder, key)
  if obj == nil then
	  return "null"
  elseif type(obj) == "boolean" then
	  return tostring(obj)
  elseif type(obj) == "number" then
	  return tostring(obj)
  elseif type(obj) == "string" then
	  return '"' .. obj:gsub('"', '\\"') .. '"'
  elseif type(obj) == "table" then
	  local isArray = true
	  local maxIndex = 0
	  for k, v in pairs(obj) do
		  if type(k) ~= "number" then
			  isArray = false
			  break
		  end
		  maxIndex = math.max(maxIndex, k)
	  end
	  if isArray then
		  local items = {}
		  for i = 1, maxIndex do
			  table.insert(items, encodeJson(obj[i], fieldOrder, key))
		  end
		  return "[" .. table.concat(items, ",") .. "]"
	  else
		  local items = {}
		  local fieldOrdering = fieldOrder[key] or {}
		  
		  -- Phase 1: ordered keys
		  for _, fieldName in ipairs(fieldOrdering) do
			  local v = obj[fieldName]
			  if v ~= nil then
				  local encoded = encodeJson(v, fieldOrder, fieldName)
				  if encoded ~= nil then
					  table.insert(items, '"' .. fieldName:gsub('"', '\\"') .. '":' .. encoded)
				  end
			  end
		  end
		  
		  -- Phase 2: remaining keys (not in fieldOrder)
		  for k, v in pairs(obj) do
			  local found = false
			  for _, fieldName in ipairs(fieldOrdering) do
				  if k == fieldName then
					  found = true
					  break
				  end
			  end
			  if not found then
				  local keyStr = type(k) == "string" and k or tostring(k)
				  local encoded = encodeJson(v, fieldOrder, keyStr)
				  if encoded ~= nil then
					  table.insert(items, '"' .. keyStr:gsub('"', '\\"') .. '":' .. encoded)
				  end
			  end
		  end
		  
		  return "{" .. table.concat(items, ",") .. "}"
	  end
  else
	  return '"' .. tostring(obj) .. '"'
  end
end

local function get_msg_field_ordering(action)
    if action == "block" then
        return BLOCK_FIELD_ORDER
    elseif action == "captcha" then
        return CAPTCHA_FIELD_ORDER
    else
        return ALLOW_FIELD_ORDER
    end
end

local function cleanupEmptyNull(obj)
    if type(obj) ~= "table" then
        if type(obj) == "string" then
            local lower = obj:lower()
            if lower == "" or lower == "null" then
                return nil
            end
        end
        return obj
    end
    for key, value in pairs(obj) do
        local cleaned = cleanupEmptyNull(value)
        if cleaned == nil then
            obj[key] = nil
        else
            obj[key] = cleaned
        end
    end
    if next(obj) == nil then
        return nil
    end
    return obj
end

local function collectUnmapped(source, target)
    for key, value in pairs(source or {}) do
        if type(value) == "table" then
            local nested = {}
            collectUnmapped(value, nested)
            if next(nested) then
                target[key] = nested
            end
        else
            target[key] = value
        end
    end
end

function processEvent(event)
    if type(event) ~= "table" then
        return nil
    end

    local MAPPED_FIELDS = {}
    local result = {}

    result.time = event.timestamp

    local source = deepCopy(event, IGNORE_KEYS)

    local action = getValueByPath(source, "action") or ""
    action = action:lower()

    
    
    for _, mapping in ipairs(FIELD_MAPPINGS) do
        local value = getValueByPath(source, mapping.source)
        if value ~= nil then
            setValueByPath(result, mapping.target, deepCopy(value))
        end
        MAPPED_FIELDS[mapping.source] = true
    end

    -- Remove mapped fields from original event for unmapped collection
    for key, _ in pairs(MAPPED_FIELDS) do
        setValueByPath(event, key, nil)
    end
    
    for key, _ in pairs(IGNORE_KEYS) do
        setValueByPath(event, key, nil)
    end

    for key, value in pairs(getConstantFields(action, source)) do
        result[key] = value
    end

    local unmapped = {}
    collectUnmapped(event, unmapped)
    if next(unmapped) then
        -- Merge with existing unmapped
        for k, v in pairs(unmapped) do
            if result.unmapped then
                result.unmapped[k] = v
            end
        end
    end

    result.message = encodeJson(source, get_msg_field_ordering(action), "message")
    result.timestamp = nil

    if FEATURES.CLEANUP_EMPTY_NULL then
        cleanupEmptyNull(result)
    end

    return result
end