-- SentinelOne Parser: akamai_general-latest 
-- OCSF Class: Security Control (2001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-16T14:56:51.650199

-- Pre-compile regex patterns for performance
local patterns = {
    ip = "^%d+%.%d+%.%d+%.%d+$",
    timestamp = "^%d%d%d%d%-%d%d%-%d%dT%d%d:%d%d:%d%dZ$"
}

-- Severity mapping table
local severity_map = {
    SQL_Injection = 4,
    Command_Injection = 4, 
    Cross_Site_Scripting = 3,
    Path_Traversal = 3,
    API_Scan = 2
}

-- Status mapping table
local status_map = {
    blocked = 2,
    denied = 2,
    alert = 1,
    logged = 1
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local variables
    local output = {
        class_uid = 2001,
        class_name = "Security Control",
        category_uid = 2, 
        category_name = "Findings",
        activity_id = 1,
        activity_name = "Security Alert",
        type_uid = 200101,
        metadata = {},
        http_request = {},
        http_response = {},
        src_endpoint = {},
        finding = {}
    }

    -- Timestamp validation and transformation
    if record.timestamp and record.timestamp:match(patterns.timestamp) then
        output.time = record.timestamp
    else
        output.time = os.date("!%Y-%m-%dT%H:%M:%SZ")
    end

    -- IP address validation and transformation
    if record.client_ip and record.client_ip:match(patterns.ip) then
        output.src_endpoint.ip = record.client_ip
        -- Generate observables
        output.observables = {
            {
                name = "src_ip",
                type = "IP Address", 
                value = record.client_ip
            }
        }
    end

    -- HTTP context mapping
    if record.host then output.http_request.hostname = record.host end
    if record.path then output.http_request.url = {path = record.path} end
    if record.http_method then output.http_request.http_method = record.http_method end
    if record.user_agent then output.http_request.user_agent = record.user_agent end
    if record.status_code then output.http_response.code = tonumber(record.status_code) end

    -- Security finding details
    if record.rule_id then output.metadata.rule_uid = record.rule_id end
    if record.attack_type then output.finding.type = record.attack_type end
    if record.action then output.disposition = record.action end
    if record.message then output.message = record.message end

    -- Map severity based on attack type
    if record.attack_type and severity_map[record.attack_type] then
        output.severity_id = severity_map[record.attack_type]
    else
        output.severity_id = 2 -- Default severity
    end

    -- Map status based on action
    if record.action and status_map[record.action] then
        output.status_id = status_map[record.action]
    end

    -- Validation of required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    return output
end