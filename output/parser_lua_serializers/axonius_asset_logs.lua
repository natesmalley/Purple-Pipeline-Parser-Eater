-- Axonius Asset Logs Parser
-- OCSF Class: Network Activity (4001)
-- Performance Level: High-volume optimized for push pipeline

-- Pre-declare locals for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_format = string.format
local string_match = string.match

-- Activity mapping for different event types
local ACTIVITY_MAP = {
    ["AssumeRole"] = 1,
    ["GetSessionToken"] = 1,
    ["CreateAccessKey"] = 2,
    ["DeleteAccessKey"] = 3,
    default = 99
}

-- Severity mapping based on error presence
local function get_severity_id(error_code, error_message)
    if error_code or error_message then
        return 4 -- High severity for errors
    end
    return 1 -- Informational for successful operations
end

-- Type UID mapping based on event category
local function get_type_uid(event_category)
    if event_category == "Management" then
        return 400101
    elseif event_category == "Data" then
        return 400102
    else
        return 400199 -- Other
    end
end

-- Timestamp parser for ISO format
local function parse_timestamp(time_str)
    if not time_str or type(time_str) ~= "string" then
        return nil
    end
    
    -- Handle ISO 8601 format: 2023-01-01T12:00:00Z
    local year, month, day, hour, min, sec = string_match(time_str, "^(%d%d%d%d)%-(%d%d)%-(%d%d)T(%d%d):(%d%d):(%d%d)")
    if year then
        local timestamp = os.time({
            year = tonumber(year),
            month = tonumber(month),
            day = tonumber(day),
            hour = tonumber(hour),
            min = tonumber(min),
            sec = tonumber(sec)
        })
        return timestamp * 1000 -- Convert to milliseconds
    end
    
    return nil
end

-- IP address validation
local function is_valid_ip(ip)
    if not ip or type(ip) ~= "string" then
        return false
    end
    local parts = {string_match(ip, "^(%d+)%.(%d+)%.(%d+)%.(%d+)$")}
    if #parts ~= 4 then
        return false
    end
    for i = 1, 4 do
        local n = tonumber(parts[i])
        if not n or n < 0 or n > 255 then
            return false
        end
    end
    return true
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with required fields
    local output = {
        class_uid = 4001,
        class_name = "Network Activity",
        category_uid = 4,
        category_name = "Network Activity",
        metadata = {
            product = {
                name = "Axonius Asset Management",
                vendor_name = "Axonius"
            },
            version = "1.0.0"
        },
        unmapped = {}
    }

    -- Timestamp processing with fallback
    local event_time = record.eventTime
    if event_time then
        local parsed_time = parse_timestamp(event_time)
        if parsed_time then
            output.time = parsed_time
        else
            output.time = os_time() * 1000
        end
    else
        output.time = os_time() * 1000
    end

    -- Activity and type mapping based on event category
    local event_category = record.eventCategory
    if event_category then
        output.type_uid = get_type_uid(event_category)
        output.category_name = event_category
        output.unmapped.event_category = event_category
    else
        output.type_uid = 400199 -- Other
    end

    -- Activity ID determination
    local activity_name = record.eventID
    if activity_name and ACTIVITY_MAP[activity_name] then
        output.activity_id = ACTIVITY_MAP[activity_name]
        output.activity_name = activity_name
    else
        output.activity_id = ACTIVITY_MAP.default
        output.activity_name = "Other"
    end

    -- Severity mapping
    output.severity_id = get_severity_id(record.errorCode, record.errorMessage)

    -- Source endpoint processing
    local source_ip = record.sourceIPAddress
    if source_ip and is_valid_ip(source_ip) then
        output.src_endpoint = {
            ip = source_ip
        }
    end

    -- User identity processing
    local user_identity = record.userIdentity
    if user_identity and type(user_identity) == "table" then
        output.actor = {
            user = {}
        }
        
        if user_identity.principalId then
            output.actor.user.uid = user_identity.principalId
        end
        
        if user_identity.type then
            output.actor.user.type = user_identity.type
        end
        
        if user_identity.accessKeyId then
            output.actor.user.credential_uid = user_identity.accessKeyId
        end
        
        -- Session context processing
        local session_context = user_identity.sessionContext
        if session_context and type(session_context) == "table" then
            local session_issuer = session_context.sessionIssuer
            if session_issuer and type(session_issuer) == "table" then
                if session_issuer.userName then
                    output.actor.user.name = session_issuer.userName
                end
                if session_issuer.principalId then
                    output.actor.user.groups = {session_issuer.principalId}
                end
            end
        end
    end

    -- Error handling
    if record.errorCode or record.errorMessage then
        output.status_id = 2 -- Failure
        output.status = "Failure"
        if record.errorCode then
            output.status_code = record.errorCode
            output.unmapped.error_code = record.errorCode
        end
        if record.errorMessage then
            output.status_detail = record.errorMessage
            output.unmapped.error_message = record.errorMessage
        end
    else
        output.status_id = 1 -- Success
        output.status = "Success"
    end

    -- Message processing
    if record.message then
        output.message = record.message
    end

    -- AWS-specific fields
    if record.awsRegion then
        output.cloud = {
            region = record.awsRegion
        }
        output.unmapped.aws_region = record.awsRegion
    end

    if record.recipientAccountId then
        if not output.cloud then
            output.cloud = {}
        end
        output.cloud.account = {
            uid = record.recipientAccountId
        }
        output.unmapped.recipient_account_id = record.recipientAccountId
    end

    -- User agent processing
    if record.userAgent then
        output.http_request = {
            user_agent = record.userAgent
        }
        output.unmapped.user_agent = record.userAgent
    end

    -- Request parameters processing
    local request_params = record.requestParameters
    if request_params and type(request_params) == "table" then
        for key, value in pairs(request_params) do
            output.unmapped["request_" .. key] = value
        end
        
        if request_params.bucketName then
            output.resource = {
                name = request_params.bucketName,
                type = "S3 Bucket"
            }
        end
        
        if request_params.instanceId then
            output.device = {
                instance_uid = request_params.instanceId
            }
        end
    end

    -- Response elements processing
    local response_elements = record.responseElements
    if response_elements and type(response_elements) == "table" then
        for key, value in pairs(response_elements) do
            if type(value) == "table" then
                for sub_key, sub_value in pairs(value) do
                    output.unmapped["response_" .. key .. "_" .. sub_key] = sub_value
                end
            else
                output.unmapped["response_" .. key] = value
            end
        end
    end

    -- TLS details processing
    local tls_details = record.tlsDetails
    if tls_details and type(tls_details) == "table" then
        output.tls = {}
        if tls_details.tlsVersion then
            output.tls.version = tls_details.tlsVersion
        end
        if tls_details.cipherSuite then
            output.tls.cipher = tls_details.cipherSuite
        end
        output.unmapped.tls_details = tls_details
    end

    -- Additional event data
    if record.additionalEventData then
        output.unmapped.additional_event_data = record.additionalEventData
    end

    -- VPC endpoint processing
    if record.vpcEndpointId then
        output.unmapped.vpc_endpoint_id = record.vpcEndpointId
    end

    -- API version
    if record.apiVersion then
        output.api = {
            version = record.apiVersion
        }
        output.unmapped.api_version = record.apiVersion
    end

    -- Event version and ID
    if record.eventVersion then
        output.unmapped.event_version = record.eventVersion
    end

    if record.eventID then
        output.unmapped.event_id = record.eventID
    end

    -- Resources processing
    local resources = record.resources
    if resources and type(resources) == "table" then
        if type(resources) == "table" and resources.accountId then
            output.unmapped.resource_account_id = resources.accountId
        end
        if type(resources) == "table" and resources.type then
            output.unmapped.resource_type = resources.type
        end
    end

    -- Generate unique identifier if not present
    if not output.uid then
        output.uid = string_format("axonius_%d_%s", output.time, output.activity_name or "unknown")
    end

    -- Raw data preservation
    output.raw_data = record

    return output
end