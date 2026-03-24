-- SentinelOne Parser: akamai_sitedefender-latest 
-- OCSF Class: HTTP Activity (4002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-16T14:57:31.551635

-- Pre-compile patterns for performance
local PATTERNS = {
    ip = "^%d+%.%d+%.%d+%.%d+$",
    method = "^[A-Z]+$"
}

-- Cached references for performance
local type = type
local pairs = pairs
local tonumber = tonumber
local os_time = os.time

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize output structure with local references
    local output = {
        -- Core OCSF fields
        class_uid = 4002,
        class_name = "HTTP Activity", 
        category_uid = 2,
        category_name = "Findings",
        type_uid = 400201,
        
        -- Nested structures
        src_endpoint = {},
        http_request = {},
        metadata = {
            product = {}
        }
    }

    -- Safe table accessor helper
    local function get_nested(t, ...)
        local current = t
        for _, k in ipairs({...}) do
            if type(current) ~= "table" then return nil end
            current = current[k]
        end
        return current
    end

    -- Process attack data
    local attack_data = record.attackData
    if type(attack_data) == "table" then
        -- Client IP validation and mapping
        local client_ip = attack_data.clientIP
        if client_ip and type(client_ip) == "string" and client_ip:match(PATTERNS.ip) then
            output.src_endpoint.ip = client_ip
        end

        -- Config and Policy IDs
        output.metadata.correlation_uid = attack_data.configId
        output.policy = {name = attack_data.policyId}

        -- Process rules array
        local rules = attack_data.rules
        if type(rules) == "table" then
            local observables = {}
            local disposition
            local message

            for _, rule in ipairs(rules) do
                if type(rule) == "table" then
                    -- Collect rule information
                    table.insert(observables, string.format("Rule: %s", rule.rule or "unknown"))
                    disposition = rule.ruleAction
                    message = rule.ruleMessage
                    
                    -- Set activity and severity based on rule action
                    if rule.ruleAction == "BLOCK" then
                        output.activity_id = 2
                        output.activity_name = "Access Denied"
                        output.severity_id = 3
                        output.severity = "High"
                    elseif rule.ruleAction == "ALERT" then
                        output.activity_id = 1
                        output.activity_name = "Access Granted" 
                        output.severity_id = 2
                        output.severity = "Medium"
                    end
                end
            end

            -- Set collected rule data
            if #observables > 0 then
                output.observables = observables
                output.disposition = disposition
                output.message = message
            end
        end
    end

    -- Process HTTP message data
    local http = record.httpMessage
    if type(http) == "table" then
        -- Validate and set HTTP method
        local method = http.method
        if method and type(method) == "string" and method:match(PATTERNS.method) then
            output.http_request.http_method = method
        end

        -- Set URL components
        output.http_request.url = {
            hostname = http.host,
            path = http.path
        }

        -- Set response code
        local status = tonumber(http.status)
        if status then
            output.http_response = {code = status}
        end
    end

    -- Process geolocation
    local geo = record.geo
    if type(geo) == "table" then
        output.src_endpoint.location = {
            city = geo.city,
            country = geo.country
        }
    end

    -- Process risk data
    local risk = record.userRiskData
    if type(risk) == "table" then
        local bot_score = tonumber(risk.botScore)
        if bot_score then
            output.risk_score = bot_score
        end
    end

    -- Set timestamp
    output.time = record.time or (os_time() * 1000)

    -- Final validation
    if not output.activity_id then
        output.activity_id = 99
        output.activity_name = "Other"
        output.severity_id = 1
        output.severity = "Low"
    end

    return output
end