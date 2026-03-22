--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: marketplace-zscalerinternetaccess-latest
  Generated: 2025-10-13T12:45:31.887176
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: marketplace-zscalerinternetaccess-latest 
-- OCSF Class: HTTP Activity (4002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:05:58.179396

-- Pre-compile patterns for performance
local PATTERNS = {
    protocol = "^[%w]+$",
    datetime = "^%d%d%d%d%-%d%d%-%d%dT%d%d:%d%d:%d%d"
}

-- Cached enum mappings
local ACTION_MAP = {
    CREATE = 1,
    READ = 2,
    UPDATE = 3,
    DELETE = 4,
    ACTIVATE = 10,
    DEACTIVATE = 11
}

-- Helper functions
local function validate_field(value, pattern)
    if not value or type(value) ~= "string" then return false end
    return string.match(value, pattern) ~= nil
end

local function safe_copy(src, dest, field, target)
    if src and src[field] then
        if not dest[target] then dest[target] = {} end
        dest[target] = src[field]
    end
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize output with required OCSF fields
    local output = {
        metadata = {
            version = "1.0.0",
            product = {
                vendor_name = "ZScaler",
                name = "Zscaler Internet Access"
            }
        },
        category_uid = 4,
        category_name = "Network Activity",
        class_uid = 4002,
        class_name = "HTTP Activity",
        time = os.time() * 1000,
        observables = {}
    }

    -- Process sourcetype-specific transformations
    if record.sourcetype == "zscalernss-web" then
        if record.event and record.event.protocol == "HTTPS" then
            -- HTTPS traffic processing
            safe_copy(record.event, output, "protocol", "http_request.url.scheme")
            safe_copy(record.event, output, "urlcategory", "http_request.url.categories")
            safe_copy(record.event, output, "useragent", "http_request.user_agent")
            
            -- Network details
            if record.event.clientpublicIP then
                output.src_endpoint = {
                    ip = record.event.clientpublicIP,
                    hostname = record.event.devicehostname
                }
            end

            -- Traffic metrics
            output.network_traffic = {
                bytes = tonumber(record.event.transactionsize) or 0,
                bytes_in = tonumber(record.event.responsesize) or 0,
                bytes_out = tonumber(record.event.requestsize) or 0
            }

            -- Status handling
            local action = record.event.action
            output.status_id = ACTION_MAP[action] or 99
            output.status_detail = record.event.reason

        elseif record.event and record.event.protocol == "FTP" then
            -- FTP traffic processing
            output.class_uid = 4008
            output.class_name = "FTP Activity"
            
            safe_copy(record.event, output, "devicehostname", "device.hostname")
            safe_copy(record.event, output, "clientpublicIP", "src_endpoint.ip")
            
            -- FTP specific metrics
            if record.event.transactionsize then
                output.network_traffic = {
                    bytes = tonumber(record.event.transactionsize)
                }
            end
        end

    elseif record.sourcetype == "zscalernss-audit" then
        -- Audit event processing
        output.class_uid = 3004
        output.class_name = "Entity Management"
        
        safe_copy(record.event, output, "adminid", "actor.user.email_addr")
        safe_copy(record.event, output, "clientip", "src_endpoint.ip")
        
        -- Audit specific fields
        output.activity_id = ACTION_MAP[record.event.action] or 99
        output.metadata.uid = record.event.recordid
    end

    -- Add observables
    if output.src_endpoint and output.src_endpoint.ip then
        table.insert(output.observables, {
            name = "src_endpoint.ip",
            type = "IP Address",
            type_id = 2,
            value = output.src_endpoint.ip
        })
    end

    -- Validation and cleanup
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    return output
end