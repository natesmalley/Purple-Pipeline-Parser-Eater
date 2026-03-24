--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: aws_waf-latest
  Generated: 2025-10-13T12:41:08.009188
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: aws_waf-latest
-- OCSF Class: HTTP Activity (4002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:14:15.925005

-- Pre-compile static patterns and lookups for performance
local ACTION_MAP = {
    ALLOW = {status_id = 1, activity_id = 1, severity_id = 1},
    BLOCK = {status_id = 2, activity_id = 2, severity_id = 4}, 
    CAPTCHA = {status_id = 99, activity_id = 3, severity_id = 3},
    COUNT = {status_id = 99, activity_id = 4, severity_id = 2}
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with static fields
    local output = {
        -- Static classifications
        class_uid = 4002,
        class_name = "HTTP Activity",
        category_uid = 4,
        category_name = "Network Activity",
        type_uid = 400201,
        
        -- Product metadata
        metadata = {
            product = {
                name = "AWS WAF",
                vendor_name = "Amazon Web Services"
            },
            version = record.formatVersion
        },
        
        -- Initialize nested structures
        src_endpoint = {},
        http_request = {
            url = {}
        }
    }

    -- Efficient field mapping using local references
    local http_request = record.httpRequest or {}
    
    -- Direct field mappings
    output.time = record.timestamp
    output.disposition = record.action
    output.firewall_rule = {
        uid = record.webaclId,
        name = record.ruleGroupId,
        type = record.terminatingRuleType
    }

    -- HTTP Request mappings
    if http_request then
        output.src_endpoint.ip = http_request.clientIp
        output.src_endpoint.location = {
            country = http_request.country
        }
        output.http_request = {
            url = {
                text = http_request.uri,
                query_string = http_request.args
            },
            http_method = http_request.httpMethod,
            version = http_request.httpVersion,
            uid = record.requestId,
            http_headers = http_request.headers
        }
    end

    -- Action-based field mappings using lookup table
    if record.action and ACTION_MAP[record.action] then
        local action_props = ACTION_MAP[record.action]
        output.status_id = action_props.status_id
        output.activity_id = action_props.activity_id 
        output.severity_id = action_props.severity_id
    end

    -- Generate observables array efficiently
    if http_request.clientIp then
        output.observables = {
            {
                name = "client_ip",
                type = "IP Address", 
                value = http_request.clientIp,
                type_id = 2
            },
            {
                name = "webacl_id",
                type = "Other",
                value = record.webaclId,
                type_id = 99
            },
            {
                name = "uri",
                type = "URL",
                value = http_request.uri,
                type_id = 23
            }
        }
    end

    -- Additional metadata
    if record.labels then
        output.metadata.labels = record.labels
    end
    
    if record.ruleGroupId then
        output.metadata.extension = {
            rule_group_id = record.ruleGroupId,
            terminating_rule_type = record.terminatingRuleType
        }
    end

    -- Validation of required fields
    if not output.time then
        output.time = os.time() * 1000
    end

    if not output.class_uid or output.class_uid == 0 then
        return nil, "Missing required class_uid"
    end

    return output
end