-- Linux System Logs to OCSF Network Activity Transformation
-- Target: OCSF Network Activity (class_uid=4001, category_uid=4)

local CLASS_UID = 4001
local CATEGORY_UID = 4

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

-- Safe value access with default
function getValue(tbl, key, default)
    local value = tbl[key]
    return value ~= nil and value or default
end

-- Replace userdata nil values
function no_nulls(d, rn)
    if type(d) == "table" then
        for k, v in pairs(d) do
            if type(v) == "userdata" then d[k] = rn
            elseif type(v) == "table" then no_nulls(v, rn) end
        end
    end
    return d
end

-- Collect unmapped fields
function copyUnmappedFields(event, mappedPaths, result)
    for k, v in pairs(event) do
        if not mappedPaths[k] and k ~= "_ob" and v ~= nil and v ~= "" then
            setNestedField(result, "unmapped." .. k, v)
        end
    end
end

-- Parse timestamp to milliseconds since epoch
function parseTimestamp(timeStr)
    if not timeStr or type(timeStr) ~= "string" then return nil end
    
    -- Try RFC3339/ISO format: 2023-01-01T12:00:00Z or 2023-01-01T12:00:00.123Z
    local yr, mo, dy, hr, mn, sc, ms = timeStr:match("(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)%.?(%d*)")
    if yr then
        local timestamp = os.time({
            year = tonumber(yr), month = tonumber(mo), day = tonumber(dy),
            hour = tonumber(hr), min = tonumber(mn), sec = tonumber(sc)
        })
        local msec = ms and #ms > 0 and tonumber(ms:sub(1, 3):ljust(3, '0')) or 0
        return timestamp * 1000 + msec
    end
    
    -- Try syslog format: Jan 01 12:00:00 or 2023 Jan 01 12:00:00
    local months = {Jan=1, Feb=2, Mar=3, Apr=4, May=5, Jun=6, Jul=7, Aug=8, Sep=9, Oct=10, Nov=11, Dec=12}
    yr, mo, dy, hr, mn, sc = timeStr:match("(%d+)%s+(%a+)%s+(%d+)%s+(%d+):(%d+):(%d+)")
    if not yr then
        mo, dy, hr, mn, sc = timeStr:match("(%a+)%s+(%d+)%s+(%d+):(%d+):(%d+)")
        yr = os.date("%Y") -- Current year if not specified
    end
    if mo and months[mo] then
        local timestamp = os.time({
            year = tonumber(yr), month = months[mo], day = tonumber(dy),
            hour = tonumber(hr), min = tonumber(mn), sec = tonumber(sc)
        })
        return timestamp * 1000
    end
    
    -- Try Unix timestamp (seconds or milliseconds)
    local unixTime = tonumber(timeStr)
    if unixTime then
        if unixTime > 1e12 then -- Already milliseconds
            return unixTime
        else -- Seconds, convert to milliseconds
            return unixTime * 1000
        end
    end
    
    return nil
end

-- Extract IP addresses from message
function extractIPs(message)
    if not message or type(message) ~= "string" then return nil, nil end
    
    local ips = {}
    -- Match IPv4 addresses
    for ip in message:gmatch("(%d+%.%d+%.%d+%.%d+)") do
        table.insert(ips, ip)
    end
    
    return ips[1], ips[2] -- Return first two IPs as src and dst
end

-- Extract ports from message
function extractPorts(message)
    if not message or type(message) ~= "string" then return nil, nil end
    
    local ports = {}
    -- Look for port patterns like :80, port 443, etc.
    for port in message:gmatch(":(%d+)") do
        table.insert(ports, tonumber(port))
    end
    for port in message:gmatch("port%s+(%d+)") do
        table.insert(ports, tonumber(port))
    end
    
    return ports[1], ports[2] -- Return first two ports as src and dst
end

-- Determine protocol from message content
function extractProtocol(message)
    if not message or type(message) ~= "string" then return nil end
    
    local msgLower = message:lower()
    if msgLower:find("tcp") then return "TCP"
    elseif msgLower:find("udp") then return "UDP"
    elseif msgLower:find("icmp") then return "ICMP"
    elseif msgLower:find("http") then return "HTTP"
    elseif msgLower:find("https") then return "HTTPS"
    elseif msgLower:find("ssh") then return "SSH"
    elseif msgLower:find("dns") then return "DNS"
    elseif msgLower:find("ftp") then return "FTP"
    end
    
    return nil
end

-- Map severity levels to OCSF severity_id
function getSeverityId(level, priority)
    if level then
        local levelStr = tostring(level):lower()
        if levelStr:find("emerg") or levelStr:find("panic") then return 5 -- Critical
        elseif levelStr:find("alert") or levelStr:find("crit") then return 5 -- Critical
        elseif levelStr:find("err") then return 4 -- High
        elseif levelStr:find("warn") then return 3 -- Medium
        elseif levelStr:find("notice") then return 2 -- Low
        elseif levelStr:find("info") then return 1 -- Informational
        elseif levelStr:find("debug") then return 1 -- Informational
        end
    end
    
    if priority then
        local pri = tonumber(priority)
        if pri then
            if pri <= 3 then return 5 -- Critical/Alert/Error
            elseif pri == 4 then return 4 -- Warning -> High
            elseif pri == 5 then return 3 -- Notice -> Medium
            elseif pri == 6 then return 1 -- Info -> Informational
            elseif pri == 7 then return 1 -- Debug -> Informational
            end
        end
    end
    
    return 0 -- Unknown
end

-- Determine activity based on message content
function getNetworkActivity(message, event)
    if not message or type(message) ~= "string" then
        return 99, "Other" -- Default activity
    end
    
    local msgLower = message:lower()
    
    -- Connection activities
    if msgLower:find("connect") or msgLower:find("established") then
        return 1, "Open"
    elseif msgLower:find("disconnect") or msgLower:find("closed") or msgLower:find("close") then
        return 2, "Close"
    elseif msgLower:find("deny") or msgLower:find("drop") or msgLower:find("block") or msgLower:find("reject") then
        return 4, "Deny"
    elseif msgLower:find("allow") or msgLower:find("accept") or msgLower:find("permit") then
        return 3, "Allow"
    elseif msgLower:find("timeout") then
        return 5, "Timeout"
    elseif msgLower:find("refuse") or msgLower:find("refused") then
        return 6, "Refuse"
    end
    
    -- Traffic activities
    if msgLower:find("traffic") or msgLower:find("packet") or msgLower:find("data") then
        return 1, "Traffic Flow"
    end
    
    return 99, "Other"
end

-- Field mappings for Linux system logs
local fieldMappings = {
    -- Basic OCSF required fields
    {type = "computed", target = "class_uid", value = CLASS_UID},
    {type = "computed", target = "category_uid", value = CATEGORY_UID},
    {type = "computed", target = "class_name", value = "Network Activity"},
    {type = "computed", target = "category_name", value = "Network Activity"},
    
    -- Common log fields
    {type = "direct", source = "message", target = "message"},
    {type = "direct", source = "raw_data", target = "raw_data"},
    {type = "direct", source = "hostname", target = "metadata.product.name"},
    {type = "direct", source = "host", target = "metadata.product.name"},
    {type = "direct", source = "program", target = "metadata.product.name"},
    {type = "direct", source = "facility", target = "metadata.labels.facility"},
    {type = "direct", source = "tag", target = "metadata.labels.tag"},
    
    -- Network endpoints
    {type = "direct", source = "src_ip", target = "src_endpoint.ip"},
    {type = "direct", source = "source_ip", target = "src_endpoint.ip"},
    {type = "direct", source = "srcip", target = "src_endpoint.ip"},
    {type = "direct", source = "dst_ip", target = "dst_endpoint.ip"},
    {type = "direct", source = "dest_ip", target = "dst_endpoint.ip"},
    {type = "direct", source = "dstip", target = "dst_endpoint.ip"},
    {type = "direct", source = "src_port", target = "src_endpoint.port"},
    {type = "direct", source = "source_port", target = "src_endpoint.port"},
    {type = "direct", source = "srcport", target = "src_endpoint.port"},
    {type = "direct", source = "dst_port", target = "dst_endpoint.port"},
    {type = "direct", source = "dest_port", target = "dst_endpoint.port"},
    {type = "direct", source = "dstport", target = "dst_endpoint.port"},
    {type = "direct", source = "src_host", target = "src_endpoint.hostname"},
    {type = "direct", source = "dst_host", target = "dst_endpoint.hostname"},
    {type = "direct", source = "protocol", target = "protocol_name"},
    {type = "direct", source = "proto", target = "protocol_name"},
    
    -- Status and counts
    {type = "direct", source = "status", target = "status"},
    {type = "direct", source = "count", target = "count"},
    {type = "direct", source = "duration", target = "duration"},
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

    -- Extract message for further processing
    local message = getValue(event, "message", "") or getValue(event, "msg", "") or getValue(event, "text", "")
    if message ~= "" then
        result.message = message
        mappedPaths["message"] = true
        mappedPaths["msg"] = true
        mappedPaths["text"] = true
    end

    -- Parse timestamp
    local eventTime = getValue(event, "timestamp", nil) or getValue(event, "time", nil) or 
                      getValue(event, "@timestamp", nil) or getValue(event, "datetime", nil) or
                      getValue(event, "date", nil)
    
    if eventTime then
        local parsedTime = parseTimestamp(eventTime)
        if parsedTime then
            result.time = parsedTime
        end
        mappedPaths["timestamp"] = true
        mappedPaths["time"] = true
        mappedPaths["@timestamp"] = true
        mappedPaths["datetime"] = true
        mappedPaths["date"] = true
    end
    
    if not result.time then
        result.time = os.time() * 1000 -- Current time as fallback
    end

    -- Extract network information from message if not directly available
    if message and message ~= "" then
        -- Extract IPs if not already set
        if not getNestedField(result, "src_endpoint.ip") or not getNestedField(result, "dst_endpoint.ip") then
            local srcIP, dstIP = extractIPs(message)
            if srcIP and not getNestedField(result, "src_endpoint.ip") then
                setNestedField(result, "src_endpoint.ip", srcIP)
            end
            if dstIP and not getNestedField(result, "dst_endpoint.ip") then
                setNestedField(result, "dst_endpoint.ip", dstIP)
            end
        end
        
        -- Extract ports if not already set
        if not getNestedField(result, "src_endpoint.port") or not getNestedField(result, "dst_endpoint.port") then
            local srcPort, dstPort = extractPorts(message)
            if srcPort and not getNestedField(result, "src_endpoint.port") then
                setNestedField(result, "src_endpoint.port", srcPort)
            end
            if dstPort and not getNestedField(result, "dst_endpoint.port") then
                setNestedField(result, "dst_endpoint.port", dstPort)
            end
        end
        
        -- Extract protocol if not already set
        if not result.protocol_name then
            local protocol = extractProtocol(message)
            if protocol then
                result.protocol_name = protocol
            end
        end
    end

    -- Determine activity and severity
    local activityId, activityName = getNetworkActivity(message, event)
    result.activity_id = activityId
    result.activity_name = activityName
    
    -- Calculate type_uid
    result.type_uid = CLASS_UID * 100 + activityId

    -- Set severity
    local level = getValue(event, "level", nil) or getValue(event, "severity", nil) or getValue(event, "priority", nil)
    local priority = getValue(event, "priority", nil) or getValue(event, "pri", nil)
    result.severity_id = getSeverityId(level, priority)
    mappedPaths["level"] = true
    mappedPaths["severity"] = true
    mappedPaths["priority"] =