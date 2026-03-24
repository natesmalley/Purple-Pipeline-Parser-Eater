-- SentinelOne Parser: pfsense_firewall_logs-latest 
-- OCSF Class: Network Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:08:48.967141

-- Pre-declare locals for performance
local type = type
local os_time = os.time
local string_format = string.format
local table_insert = table.insert

-- Validation patterns
local PATTERNS = {
    ipv4 = "^%d+%.%d+%.%d+%.%d+$",
    port = "^%d+$"
}

-- Error messages
local ERRORS = {
    invalid_input = "Invalid input record",
    missing_required = "Missing required field: %s",
    invalid_format = "Invalid format for field: %s"
}

-- Field validation helper
local function validate_field(value, pattern, field_name)
    if not value then return true end -- Skip if optional
    if not string.match(value, pattern) then
        return false, string_format(ERRORS.invalid_format, field_name)
    end
    return true
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, ERRORS.invalid_input
    end

    -- Initialize OCSF-compliant output structure with local reference
    local output = {
        class_uid = 1001,
        class_name = "Network Activity",
        category_uid = 1, 
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = 100101,
        metadata = {
            version = "1.0.0",
            product = {
                name = "pfSense",
                vendor_name = "pfSense",
                feature = {
                    name = "Firewall"
                }
            }
        }
    }

    -- Copy raw event with validation
    if record.raw_log then
        output.raw_event = record.raw_log
    end

    -- Extract and validate network fields if present
    if record.src_ip then
        local valid, err = validate_field(record.src_ip, PATTERNS.ipv4, "src_ip")
        if valid then
            output.src_endpoint = {ip = record.src_ip}
        else
            return nil, err
        end
    end

    if record.dst_ip then
        local valid, err = validate_field(record.dst_ip, PATTERNS.ipv4, "dst_ip")
        if valid then
            output.dst_endpoint = {ip = record.dst_ip}
        else
            return nil, err
        end
    end

    -- Handle ports if present
    if record.src_port then
        local valid, err = validate_field(record.src_port, PATTERNS.port, "src_port")
        if valid then
            output.src_endpoint = output.src_endpoint or {}
            output.src_endpoint.port = tonumber(record.src_port)
        else
            return nil, err
        end
    end

    if record.dst_port then
        local valid, err = validate_field(record.dst_port, PATTERNS.port, "dst_port")
        if valid then
            output.dst_endpoint = output.dst_endpoint or {}
            output.dst_endpoint.port = tonumber(record.dst_port)
        else
            return nil, err
        end
    end

    -- Add timestamp if not present
    if not output.time then
        output.time = os_time() * 1000 -- Convert to milliseconds
    end

    -- Final validation
    if not output.class_uid or output.class_uid == 0 then
        return nil, string_format(ERRORS.missing_required, "class_uid")
    end

    return output
end