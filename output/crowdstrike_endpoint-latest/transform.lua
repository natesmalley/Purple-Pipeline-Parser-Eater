-- CrowdStrike Endpoint Parser: crowdstrike_endpoint-latest 
-- OCSF Class: Security Finding (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:57:11.669920

-- Pre-compile patterns for performance
local patterns = {
    key_pattern = "\\w+",
    value_pattern = "[\\w\\s]+"
}

-- Cached severity mapping for performance
local severity_map = {
    ["Low"] = 1,
    ["Medium"] = 5, 
    ["High"] = 8,
    ["Critical"] = 10
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local vars
    local output = {
        class_uid = 1001,
        class_name = "Security Finding",
        category_uid = 1,
        category_name = "Findings",
        activity_id = 1,
        type_uid = 100101,
        observer = {},
        event = {}
    }

    -- Optimized field transformations using local vars
    local deviceVendor = record.deviceVendor
    local deviceProduct = record.deviceProduct
    local signatureID = record.signatureID
    local severity = record.severity

    -- Observer fields transformation
    if deviceVendor then
        output.observer.vendor_name = deviceVendor
    end

    if deviceProduct then
        output.observer.product_name = deviceProduct
    end

    -- Event fields transformation
    if signatureID then
        output.event.uid = signatureID
    end

    -- Optimized severity casting with mapping
    if severity then
        output.severity = severity_map[severity] or tonumber(severity) or 0
    end

    -- Metadata enrichment
    output.metadata = {
        version = "1.0.0",
        product = {
            feature = {
                name = "CrowdStrike Endpoint Security",
                uid = 1001
            }
        }
    }

    -- Time handling
    local event_time = record.rt or record.time
    if event_time then
        -- Convert to milliseconds if needed
        output.time = tonumber(event_time) * (string.len(event_time) <= 10 and 1000 or 1)
    else
        output.time = os.time() * 1000
    end

    -- Validation of required fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Missing required class_uid"
    end

    if not output.observer.vendor_name then
        output.observer.vendor_name = "CrowdStrike"
    end

    -- Custom field enrichment
    output.observo = {
        parser_id = "crowdstrike_endpoint-latest",
        ingestion_time = os.time() * 1000
    }

    -- Error handling wrapper
    local status, result = pcall(function()
        -- Additional transformations if needed
        if record.extension then
            local ext = record.extension
            if type(ext) == "string" then
                -- Parse extension fields if present
                for k, v in string.gmatch(ext, "(%w+)=([^%s]+)") do
                    output[k] = v
                end
            end
        end
    end)

    if not status then
        -- Log error but continue processing
        output.parse_error = tostring(result)
    end

    return output
end

-- Utility functions for performance optimization
local function validate_record(record)
    return record and type(record) == "table"
end

local function safe_cast_number(value)
    if not value then return nil end
    local num = tonumber(value)
    return num
end