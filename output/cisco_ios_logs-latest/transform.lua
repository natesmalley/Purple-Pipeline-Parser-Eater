-- SentinelOne Parser: cisco_ios_logs-latest 
-- OCSF Class: Network Activity (4001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:54:08.145403

-- Pre-compile patterns for performance
local PATTERNS = {
    ip = "^%d+%.%d+%.%d+%.%d+$",
    severity = "^(emerg|alert|crit|err|warning|notice|info|debug)$"
}

-- Severity mapping table for O(1) lookup
local SEVERITY_MAP = {
    emerg = 5,
    alert = 4, 
    crit = 4,
    err = 3,
    warning = 3,
    notice = 2,
    info = 1,
    debug = 1
}

-- Interface status mapping
local STATUS_MAP = {
    up = 1,
    down = 2
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize output structure with required OCSF fields
    local output = {
        class_uid = 4001,
        class_name = "Network Activity",
        category_uid = 4, 
        category_name = "Network Activity",
        metadata = {},
        device = {},
        observables = {}
    }

    -- Timestamp handling with validation
    if record.timestamp then
        output.time = record.timestamp
    else
        output.time = os.time() * 1000
    end

    -- Device information processing
    if record.hostname then
        output.device.hostname = record.hostname
    end

    if record.device_ip then
        if string.match(record.device_ip, PATTERNS.ip) then
            output.device.ip = record.device_ip
            -- Add to observables
            table.insert(output.observables, {
                name = "device_ip",
                type = "IP Address", 
                value = record.device_ip
            })
        end
    end

    -- Severity mapping with validation
    if record.severity and SEVERITY_MAP[record.severity] then
        output.severity_id = SEVERITY_MAP[record.severity]
    end

    -- Interface event handling
    if record.interface_name then
        output.device.interface_name = record.interface_name
        output.type_uid = 400102
        output.activity_id = 2
        output.activity_name = "Interface Change"
        
        if record.interface_status then
            output.status = record.interface_status
            output.status_id = STATUS_MAP[record.interface_status:lower()] or 0
        end
    else
        -- Default to general syslog
        output.type_uid = 400199
        output.activity_id = 99
        output.activity_name = "Other"
    end

    -- Message and metadata handling
    if record.message then
        output.message = record.message
    end

    if record.raw_message then
        output.raw_data = record.raw_message
    end

    if record.facility_mnemonic then
        output.metadata.product = {
            feature = {
                name = record.facility_mnemonic
            }
        }
    end

    if record.sequence_number then
        output.metadata.sequence = tonumber(record.sequence_number)
    end

    if record.mnemonic then
        output.type_name = record.mnemonic
    end

    -- Final validation
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    return output
end