-- SentinelOne Parser: akamai_dns-latest
-- OCSF Class: DNS Activity (4003)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-16T14:56:34.806550

-- Pre-compile patterns for performance
local PATTERNS = {
    ip = "^%d+%.%d+%.%d+%.%d+$",
    dns_code = "^(NOERROR|NXDOMAIN|SERVFAIL|FORMERR|REFUSED)$"
}

-- Status code mapping table
local STATUS_CODES = {
    NOERROR = 1,
    NXDOMAIN = 2,
    SERVFAIL = 2,
    FORMERR = 2,
    REFUSED = 2
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure with local variables
    local output = {
        class_uid = 4003,
        class_name = "DNS Activity", 
        category_uid = 4,
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = 400301,
        severity_id = 1,
        status_id = 1,
        
        -- Initialize nested structures
        src_endpoint = {},
        dst_endpoint = {},
        query = {},
        response = {},
        answers = {},
        metadata = {},
        observables = {}
    }

    -- Efficient field mapping with validation
    local function safe_copy(src_field, dest_table, dest_field)
        local value = record[src_field]
        if value and value ~= "" then
            if type(dest_table) == "table" then
                dest_table[dest_field] = value:match('^"?(.-)"?$') -- Strip quotes if present
            end
        end
    end

    -- Core field mappings
    safe_copy("timestamp", output, "time")
    safe_copy("client_ip", output.src_endpoint, "ip")
    safe_copy("resolver_ip", output.dst_endpoint, "ip") 
    safe_copy("domain", output.query, "hostname")
    safe_copy("record_type", output.query, "type")
    safe_copy("response_code", output.response, "code")
    safe_copy("answer", output.answers, "address")
    safe_copy("ttl", output.answers, "ttl")
    safe_copy("bytes", output.response, "length")
    safe_copy("edge_server", output.metadata, "log_name")
    safe_copy("stream_id", output.metadata, "correlation_uid")

    -- Response code processing
    if record.response_code then
        local status = STATUS_CODES[record.response_code]
        if status then
            output.status_id = status
            output.severity_id = status
        end
    end

    -- Generate observables
    if record.domain then
        output.observables = {
            {
                name = "query_hostname",
                type = "Hostname", 
                value = record.domain:match('^"?(.-)"?$')
            }
        }
    end

    -- Validation of critical fields
    if not output.query.hostname then
        return nil, "Missing required field: domain"
    end

    -- IP address validation
    if output.src_endpoint.ip and not output.src_endpoint.ip:match(PATTERNS.ip) then
        output.src_endpoint.ip = nil -- Clear invalid IP
    end

    -- Convert numeric fields
    if output.answers.ttl then
        output.answers.ttl = tonumber(output.answers.ttl) or 0
    end
    if output.response.length then
        output.response.length = tonumber(output.response.length) or 0
    end

    return output
end