-- Akamai DNS Parser: akamai_dns-latest
-- OCSF Class: DNS Activity (4003)
-- Performance Level: High-volume optimized
-- Generated for syslog ingestion mode

-- Pre-declare locals for performance
local type = type
local tonumber = tonumber
local tostring = tostring
local os_time = os.time
local string_match = string.match
local string_gsub = string.gsub

-- Pre-compile patterns for performance
local PATTERNS = {
    ip = "^%d+%.%d+%.%d+%.%d+$",
    timestamp = "%d+",
    quoted_field = '^"(.-)"$'
}

-- DNS response code mapping to OCSF status
local DNS_STATUS_MAP = {
    NOERROR = {status_id = 1, severity_id = 1},
    NXDOMAIN = {status_id = 2, severity_id = 2},
    SERVFAIL = {status_id = 2, severity_id = 3},
    FORMERR = {status_id = 2, severity_id = 2},
    REFUSED = {status_id = 2, severity_id = 2},
    NOTIMPL = {status_id = 2, severity_id = 2},
    YXDOMAIN = {status_id = 2, severity_id = 2},
    YXRRSET = {status_id = 2, severity_id = 2},
    NXRRSET = {status_id = 2, severity_id = 2},
    NOTAUTH = {status_id = 2, severity_id = 2},
    NOTZONE = {status_id = 2, severity_id = 2}
}

-- Helper function to strip quotes from fields
local function strip_quotes(value)
    if not value then return nil end
    local str_val = tostring(value)
    local stripped = string_match(str_val, PATTERNS.quoted_field)
    return stripped or str_val
end

-- Helper function to validate IP addresses
local function is_valid_ip(ip)
    if not ip then return false end
    return string_match(tostring(ip), PATTERNS.ip) ~= nil
end

-- Helper function to parse timestamp
local function parse_timestamp(ts)
    if not ts then return nil end
    local num_ts = tonumber(ts)
    if num_ts then
        -- Handle both seconds and milliseconds
        return num_ts > 1000000000000 and num_ts or (num_ts * 1000)
    end
    return nil
end

function process(event, emit)
    -- Input validation with early return
    if not event or type(event) ~= "table" then
        return
    end

    -- Parse timestamp first to set time field
    local event_time = os_time() * 1000
    local timestamp_value = event.timestamp or event.time or event.event_time or event.ts
    if timestamp_value then
        local parsed_time = parse_timestamp(timestamp_value)
        if parsed_time then
            event_time = parsed_time
        end
    end

    -- Determine activity and severity from response code
    local response_code = strip_quotes(event.response_code or event.rcode or event.status)
    local event_activity_id = 6
    local event_severity_id = 1
    local event_type_uid = 400306
    
    if response_code then
        local status_info = DNS_STATUS_MAP[response_code]
        if status_info then
            event_severity_id = status_info.severity_id
            event_activity_id = status_info.status_id == 1 and 6 or 5
            event_type_uid = status_info.status_id == 1 and 400306 or 400305
        end
    end

    -- Create event table with ALL required OCSF fields set as direct properties
    event.activity_id = event_activity_id
    event.category_uid = 4
    event.class_uid = 4003
    event.severity_id = event_severity_id
    event.time = event_time
    event.type_uid = event_type_uid

    -- Set additional standard OCSF fields
    event.activity_name = event_activity_id == 6 and "Traffic" or "Query"
    event.category_name = "Network Activity"
    event.class_name = "DNS Activity"
    event.type_name = event_type_uid == 400306 and "DNS Activity: Traffic" or "DNS Activity: Query"
    event.status_id = 1

    -- Initialize metadata if not present
    if not event.metadata then
        event.metadata = {}
    end
    if not event.metadata.product then
        event.metadata.product = {}
    end
    event.metadata.product.name = "Akamai DNS"
    event.metadata.product.vendor_name = "Akamai"
    event.metadata.version = "1.0.0"

    -- Preserve original raw data
    if event.message then
        event.raw_data = event.message
    end

    -- Map DNS query information
    local query_table = {}
    if event.domain or event.query_name or event.hostname then
        query_table.hostname = strip_quotes(event.domain or event.query_name or event.hostname)
    end
    if event.record_type or event.query_type or event.qtype then
        query_table.type = strip_quotes(event.record_type or event.query_type or event.qtype)
    end
    if event.query_class or event.qclass then
        query_table.class = strip_quotes(event.query_class or event.qclass)
    end
    
    if query_table.hostname then
        event.query = query_table
    end

    -- Map source endpoint (client)
    local src_endpoint = {}
    if event.client_ip or event.src_ip or event.source_ip then
        local client_ip = strip_quotes(event.client_ip or event.src_ip or event.source_ip)
        if is_valid_ip(client_ip) then
            src_endpoint.ip = client_ip
        end
    end
    if event.client_port or event.src_port or event.source_port then
        src_endpoint.port = tonumber(event.client_port or event.src_port or event.source_port)
    end
    
    if src_endpoint.ip then
        event.src_endpoint = src_endpoint
    end

    -- Map destination endpoint (resolver)
    local dst_endpoint = {}
    if event.resolver_ip or event.dst_ip or event.destination_ip or event.server_ip then
        local resolver_ip = strip_quotes(event.resolver_ip or event.dst_ip or event.destination_ip or event.server_ip)
        if is_valid_ip(resolver_ip) then
            dst_endpoint.ip = resolver_ip
        end
    end
    if event.resolver_port or event.dst_port or event.destination_port then
        dst_endpoint.port = tonumber(event.resolver_port or event.dst_port or event.destination_port)
    end
    
    if dst_endpoint.ip then
        event.dst_endpoint = dst_endpoint
    end

    -- Set status details
    if response_code then
        local status_info = DNS_STATUS_MAP[response_code]
        if status_info then
            event.status_id = status_info.status_id
        end
        event.status_detail = response_code
    end

    -- Map DNS answers/responses
    if event.answer or event.response_data or event.rdata then
        local answer_data = strip_quotes(event.answer or event.response_data or event.rdata)
        event.answers = {{
            rdata = answer_data,
            ttl = tonumber(event.ttl),
            type = query_table.type
        }}
    end

    -- Map additional fields
    if event.bytes or event.response_size or event.size then
        event.response = {
            length = tonumber(event.bytes or event.response_size or event.size)
        }
    end

    if event.duration or event.response_time then
        event.duration = tonumber(event.duration or event.response_time)
    end

    -- Map Akamai-specific metadata
    if event.edge_server or event.server_name then
        event.metadata.log_name = strip_quotes(event.edge_server or event.server_name)
    end
    if event.stream_id or event.request_id then
        event.metadata.correlation_uid = strip_quotes(event.stream_id or event.request_id)
    end

    -- Map connection information
    if event.protocol or event.transport then
        event.connection_info = {
            protocol_name = string_gsub(tostring(event.protocol or event.transport), "^%l", string.upper)
        }
    end

    -- Handle timezone offset
    if event.timezone or event.tz then
        event.timezone_offset = tonumber(event.timezone or event.tz)
    end

    -- Collect unmapped fields for debugging/future enhancement
    local mapped_fields = {
        timestamp = true, time = true, event_time = true, ts = true,
        domain = true, query_name = true, hostname = true,
        record_type = true, query_type = true, qtype = true,
        query_class = true, qclass = true,
        client_ip = true, src_ip = true, source_ip = true,
        client_port = true, src_port = true, source_port = true,
        resolver_ip = true, dst_ip = true, destination_ip = true, server_ip = true,
        resolver_port = true, dst_port = true, destination_port = true,
        response_code = true, rcode = true, status = true,
        answer = true, response_data = true, rdata = true,
        ttl = true, bytes = true, response_size = true, size = true,
        duration = true, response_time = true,
        edge_server = true, server_name = true,
        stream_id = true, request_id = true,
        protocol = true, transport = true,
        timezone = true, tz = true,
        message = true,
        -- OCSF fields we've added
        activity_id = true, category_uid = true, class_uid = true,
        severity_id = true, type_uid = true, activity_name = true,
        category_name = true, class_name = true, type_name = true,
        status_id = true, metadata = true, raw_data = true,
        query = true, src_endpoint = true, dst_endpoint = true,
        status_detail = true, answers = true, response = true,
        connection_info = true, timezone_offset = true
    }

    local unmapped = {}
    for key, value in pairs(event) do
        if not mapped_fields[key] and value and value ~= "" then
            unmapped[key] = value
        end
    end
    
    if next(unmapped) then
        event.unmapped = unmapped
    end

    -- Final validation - ensure required fields are present
    if not event.query or not event.query.hostname then
        event.status_detail = "Missing DNS query information"
        event.severity_id = 3
    end

    -- Emit the transformed event
    emit(event)
end