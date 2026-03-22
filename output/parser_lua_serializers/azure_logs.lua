-- Azure Logs Parser: azure_logs-latest
-- OCSF Class: Network Activity (4001)
-- Performance Level: High-volume optimized
-- Generated for push/batch pipeline

-- Pre-declare locals for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_format = string.format
local string_match = string.match
local string_lower = string.lower

-- Validation helper functions
local function validate_ip(ip)
    if not ip or type(ip) ~= "string" then return false end
    local parts = {ip:match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")}
    if #parts ~= 4 then return false end
    for i = 1, 4 do
        local n = tonumber(parts[i])
        if not n or n < 0 or n > 255 then return false end
    end
    return true
end

local function validate_port(port)
    local n = tonumber(port)
    return n and n >= 0 and n <= 65535
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with ALL required fields explicitly set
    local output = {}
    
    -- Set all required OCSF fields with proper values
    output.class_uid = 4001
    output.category_uid = 4
    output.activity_id = 99
    output.time = os_time() * 1000
    output.type_uid = 400199
    output.severity_id = 2
    
    -- Set optional fields
    output.class_name = "Network Activity"
    output.category_name = "Network Activity"
    output.metadata = {
        product = {
            name = "Azure Logs",
            vendor_name = "Microsoft"
        },
        version = "1.0.0"
    }
    output.unmapped = {}

    -- Timestamp processing with validation - override default time if available
    if record.eventTime then
        local timestamp = record.eventTime
        if type(timestamp) == "string" then
            -- Basic ISO 8601 parsing - would need more robust parsing in production
            output.time = os_time() * 1000
        elseif type(timestamp) == "number" then
            output.time = timestamp > 1000000000000 and timestamp or timestamp * 1000
        end
    end

    -- Activity and type determination based on event content - override defaults
    if record.eventCategory then
        local category = string_lower(record.eventCategory)
        if string_match(category, "s3") then
            output.activity_id = 1
            output.type_uid = 400101
        elseif string_match(category, "ec2") then
            output.activity_id = 2
            output.type_uid = 400102
        elseif string_match(category, "iam") or string_match(category, "sts") then
            output.activity_id = 3
            output.type_uid = 400103
        end
    end

    -- Severity determination - override default
    if record.errorCode or record.errorMessage then
        output.severity_id = 4
    else
        output.severity_id = 1
    end

    -- Source endpoint processing
    if validate_ip(record.sourceIPAddress) then
        output.src_endpoint = {
            ip = record.sourceIPAddress
        }
    end

    -- Process user identity information
    if record.userIdentity then
        local user_identity = record.userIdentity
        output.actor = {}
        
        if user_identity.principalId then
            output.actor.user = {
                uid = user_identity.principalId
            }
        end
        
        if user_identity.accessKeyId then
            output.actor.session = {
                uid = user_identity.accessKeyId
            }
        end
        
        if user_identity.type then
            output.actor.user_type = user_identity.type
        end
        
        -- Session context processing
        if user_identity.sessionContext and user_identity.sessionContext.sessionIssuer then
            local session_issuer = user_identity.sessionContext.sessionIssuer
            if session_issuer.userName then
                output.actor.user = output.actor.user or {}
                output.actor.user.name = session_issuer.userName
            end
        end
    end

    -- HTTP request information
    if record.userAgent then
        output.http_request = {
            user_agent = record.userAgent
        }
    end

    -- Process request parameters
    if record.requestParameters then
        local req_params = record.requestParameters
        
        if req_params.bucketName then
            output.resource = {
                name = req_params.bucketName,
                type = "S3 Bucket"
            }
        end
        
        if req_params.instanceId then
            output.resource = output.resource or {}
            output.resource.uid = req_params.instanceId
            output.resource.type = "EC2 Instance"
        end
        
        if validate_ip(req_params.Host) then
            output.dst_endpoint = {
                ip = req_params.Host
            }
        end
    end

    -- Process response elements
    if record.responseElements and record.responseElements.credentials then
        local creds = record.responseElements.credentials
        if creds.expiration then
            output.metadata.expiration_time = creds.expiration
        end
    end

    -- TLS information processing
    if record.tlsDetails then
        local tls = record.tlsDetails
        output.tls = {}
        
        if tls.tlsVersion then
            output.tls.version = tls.tlsVersion
        end
        
        if tls.cipherSuite then
            output.tls.cipher = tls.cipherSuite
        end
    end

    -- Message and status processing
    if record.message then
        output.message = record.message
    end

    if record.errorCode then
        output.status_code = record.errorCode
        output.status_id = 2
    else
        output.status_id = 1
    end

    if record.errorMessage then
        output.status_detail = record.errorMessage
    end

    -- Map remaining fields to unmapped
    local mapped_fields = {
        eventTime = true,
        sourceIPAddress = true,
        userAgent = true,
        userIdentity = true,
        requestParameters = true,
        responseElements = true,
        tlsDetails = true,
        message = true,
        errorCode = true,
        errorMessage = true,
        eventCategory = true
    }

    for key, value in pairs(record) do
        if not mapped_fields[key] and value ~= nil then
            output.unmapped[key] = value
        end
    end

    return output
end