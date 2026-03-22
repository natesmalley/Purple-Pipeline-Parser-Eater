-- SentinelOne Parser: isc_dhcp-latest
-- OCSF Class: Network Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:02:36.931300

-- Pre-declare locals for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_format = string.format

-- Constants
local CLASS_UID = 1001
local CATEGORY_UID = 1
local TYPE_UID = 100101

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure with local reference
    local output = {
        -- Core OCSF fields
        class_uid = CLASS_UID,
        class_name = "Network Activity", 
        category_uid = CATEGORY_UID,
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = TYPE_UID,
        
        -- Metadata
        metadata = {
            product = {
                name = "DHCP Server",
                vendor_name = "ISC"
            },
            version = "1.0.0"
        }
    }

    -- Safe timestamp extraction and conversion
    local timestamp = record.unmapped and record.unmapped.timestamp
    if timestamp then
        -- Convert ISO8601 to epoch seconds
        local epoch = tonumber(timestamp)
        if epoch then
            output.time = epoch
        else
            -- Fallback to current time if conversion fails
            output.time = os_time() * 1000
            output.parsing_error = string_format("Invalid timestamp format: %s", timestamp)
        end
    else
        output.time = os_time() * 1000
    end

    -- DHCP-specific field processing
    if record.unmapped then
        -- Safe field extractions with type validation
        local ip = record.unmapped.ip_address
        if ip and type(ip) == "string" then
            output.src_ip = ip
        end

        local mac = record.unmapped.mac_address 
        if mac and type(mac) == "string" then
            output.src_mac = string.lower(mac) -- Normalize MAC address
        end

        local lease_time = record.unmapped.lease_duration
        if lease_time then
            output.lease_duration = tonumber(lease_time) or 0
        end
    end

    -- Validation of required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    -- Add observability metadata
    output.observo = {
        parser_version = "1.0.0",
        processing_time = os_time()
    }

    return output
end

-- Error handler wrapper
local function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end

-- Export transform function
return {
    transform = safe_transform
}