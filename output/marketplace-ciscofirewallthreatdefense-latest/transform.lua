--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: marketplace-ciscofirewallthreatdefense-latest
  Generated: 2025-10-13T12:44:26.230574
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: marketplace-ciscofirewallthreatdefense-latest 
-- OCSF Class: Network Activity (4001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:05:50.159342

-- Pre-compile patterns for performance
local PATTERNS = {
    timestamp = "^%d%d%d%d%-%d%d%-%d%dT%d%d:%d%d:%d%dZ$",
    ip = "^%d+%.%d+%.%d+%.%d+$"
}

-- Cached string operations
local str_match = string.match
local str_format = string.format
local tbl_insert = table.insert

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local references
    local output = {
        -- Core OCSF fields
        class_uid = 4001,
        class_name = "Network Activity", 
        category_uid = 4,
        category_name = "Network Activity",
        type_uid = 400199,
        type_name = "Network Activity: Other",
        severity_id = 0,
        
        -- Initialize nested structures
        src_endpoint = {},
        dst_endpoint = {},
        observables = {},
        connection_info = {},
        traffic = {},
        metadata = {},
        unmapped = {}
    }

    -- Efficient field mapping with validation
    local function safe_copy(src_field, dest_field, validation_pattern)
        if record[src_field] then
            if not validation_pattern or str_match(record[src_field], validation_pattern) then
                output[dest_field] = record[src_field]
                return true
            end
        end
        return false
    end

    -- IP Address Handling
    if record.SrcIP then
        output.src_endpoint.ip = record.SrcIP
        -- Add observable
        tbl_insert(output.observables, {
            name = "source_ip",
            value = record.SrcIP,
            type_id = "2"
        })
    end

    if record.DstIP then
        output.dst_endpoint.ip = record.DstIP
        tbl_insert(output.observables, {
            name = "destination_ip", 
            value = record.DstIP,
            type_id = "2"
        })
    end

    -- Port Handling
    if record.SrcPort then
        output.src_endpoint.port = tonumber(record.SrcPort)
    end
    
    if record.DstPort then
        output.dst_endpoint.port = tonumber(record.DstPort)
    end

    -- Connection Info
    if record.Protocol then
        output.connection_info.protocol_name = record.Protocol
    end

    if record.ConnectionID then
        output.connection_info.uid = record.ConnectionID
    end

    -- Traffic Metrics
    if record.InitiatorBytes then
        output.traffic.bytes_out = tonumber(record.InitiatorBytes)
    end
    
    if record.ResponderBytes then
        output.traffic.bytes_in = tonumber(record.ResponderBytes)
    end

    -- User Information
    if record.User then
        output.actor = output.actor or {}
        output.actor.user = {name = record.User}
        tbl_insert(output.observables, {
            name = "user_name",
            value = record.User,
            type_id = "4"
        })
    end

    -- Event Classification
    if record.metadata and record.metadata.event_code then
        output.activity_name = record.metadata.event_code
        output.event = {type = record.metadata.event_code}
    end

    -- Status and Duration
    if record.AccessControlRuleAction then
        output.status = record.AccessControlRuleAction
    end

    if record.ConnectionDuration then
        output.duration = tonumber(record.ConnectionDuration)
    end

    -- Timestamp Handling
    if record.FirstPacketSecond then
        if str_match(record.FirstPacketSecond, PATTERNS.timestamp) then
            output.metadata.original_time = record.FirstPacketSecond
        end
    end

    -- Validation of required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Missing required OCSF classification"
    end

    -- Add default timestamp if missing
    if not output.metadata.original_time then
        output.metadata.original_time = os.date("!%Y-%m-%dT%H:%M:%SZ")
    end

    return output
end

-- Error wrapper for production use
function transform_wrapper(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, str_format("Transform error: %s", result)
    end
    return result
end