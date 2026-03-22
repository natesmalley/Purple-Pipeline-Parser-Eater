-- SentinelOne Parser: axonius_asset_logs-latest 
-- OCSF Class: Asset Inventory (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:51:54.295832

-- Pre-declare locals for performance
local type = type
local pairs = pairs
local os_time = os.time
local string_format = string.format

-- Validation helper functions
local function validate_record(record)
    if not record or type(record) ~= "table" then
        return false, "Invalid input record"
    end
    return true
end

local function validate_output(output)
    if not output.class_uid or output.class_uid == 0 then
        return false, "Missing required OCSF class_uid"
    end
    return true
end

-- Main transform function
function transform(record)
    -- Input validation with early return
    local valid, err = validate_record(record)
    if not valid then
        return nil, err
    end

    -- Initialize OCSF-compliant output structure with local references
    local output = {
        class_uid = 1001,
        class_name = "Asset Inventory", 
        category_uid = 1,
        category_name = "Asset Management",
        activity_id = 1,
        type_uid = 100101,
        metadata = {
            version = "1.0.0",
            product = {
                name = "Axonius Asset Management",
                vendor_name = "Axonius"
            }
        }
    }

    -- Performance-optimized field transformations
    local asset_data = record.root
    if asset_data then
        -- Deep copy asset data while sanitizing
        output.asset = {}
        for k,v in pairs(asset_data) do
            if type(v) ~= "function" and type(v) ~= "userdata" then
                output.asset[k] = v
            end
        end
    end

    -- Add observability fields
    output.observability = {
        parser_id = "axonius_asset_logs-latest",
        ingestion_time = os_time() * 1000
    }

    -- Timestamp handling
    if not output.time then
        output.time = output.observability.ingestion_time
    end

    -- Final validation
    local valid, err = validate_output(output)
    if not valid then
        return nil, err
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