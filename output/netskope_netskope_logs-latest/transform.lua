--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: netskope_netskope_logs-latest
  Generated: 2025-10-13T11:44:24.240829
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: netskope_netskope_logs-latest 
-- OCSF Class: Security Finding (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T11:10:32.996370

-- Pre-compile patterns for performance
local PATTERNS = {
    timestamp = "^%d+%.?%d*$",
    ip = "^%d+%.%d+%.%d+%.%d+$"
}

-- Cached references for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_format = string.format

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local references
    local output = {
        -- Core OCSF fields
        class_uid = 1001,
        class_name = "Security Finding",
        category_uid = 1, 
        category_name = "Security Events",
        metadata = {
            version = "1.0.0",
            product = {
                name = "Netskope Security Cloud",
                vendor = "Netskope"
            }
        }
    }

    -- Security Finding mappings
    local security_finding = {}
    if record._event_id then security_finding.activity_id = record._event_id end
    if record._id then security_finding.type_uid = record._id end
    if record.action then security_finding.action = record.action end
    if record.category then security_finding.category_name = record.category end
    if record._category_id then security_finding.category_uid = record._category_id end
    if record.severity_level then security_finding.severity = record.severity_level end
    if record.timestamp then
        local ts = tonumber(record.timestamp)
        if ts then security_finding.time = ts * 1000 end
    end
    output.security_finding = security_finding

    -- Geo coordinates mapping
    local geo = {}
    if record.src_latitude then geo.src_latitude = tonumber(record.src_latitude) end
    if record.src_longitude then geo.src_longitude = tonumber(record.src_longitude) end
    if record.dst_latitude then geo.dst_latitude = tonumber(record.dst_latitude) end
    if record.dst_longitude then geo.dst_longitude = tonumber(record.dst_longitude) end
    if next(geo) then output.geo_coordinates = geo end

    -- File metadata mapping
    local file = {}
    if record.file_name then file.name = record.file_name end
    if record.file_size then file.size = tonumber(record.file_size) end
    if record.file_type then file.type = record.file_type end
    if record.md5 then file.md5 = record.md5 end
    if record.local_sha256 then file.local_sha256 = record.local_sha256 end
    if next(file) then output.file = file end

    -- Network info mapping
    if record.srcip or record.dstip then
        output.network_connection_info = {
            src_ip = record.srcip,
            dst_ip = record.dstip,
            protocol_name = record.protocol
        }
    end

    -- User info mapping
    if record.user or record.user_id then
        output.user = {
            name = record.user,
            uid = record.user_id,
            ip = record.userip
        }
    end

    -- DLP info mapping
    if record.dlp_incident_id then
        output.dlp = {
            incident_id = record.dlp_incident_id,
            rule = record.dlp_rule,
            rule_count = tonumber(record.dlp_rule_count),
            file_name = record.dlp_file
        }
    end

    -- Validation and cleanup
    if not output.security_finding.time then
        output.security_finding.time = os_time() * 1000
    end

    -- Remove empty tables
    for k,v in pairs(output) do
        if type(v) == "table" and not next(v) then
            output[k] = nil
        end
    end

    return output
end

-- Error wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end