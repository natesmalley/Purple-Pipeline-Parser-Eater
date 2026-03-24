-- SentinelOne Parser: hashicorp_hcp_vault_logs-latest 
-- OCSF Class: Entity Management (3004)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:01:25.225226

-- Pre-declare locals for performance
local type = type
local pairs = pairs
local os_time = os.time
local string_format = string.format
local table_insert = table.insert

-- Validation helper functions
local function validate_string(value)
    return type(value) == "string" and #value > 0
end

local function validate_number(value) 
    return type(value) == "number"
end

-- Activity ID mapping
local ACTIVITY_MAP = {
    create = 1,
    read = 2, 
    update = 3,
    delete = 4
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize output with required OCSF fields
    local output = {
        metadata = {},
        unmapped = {},
        class_uid = 3004,
        class_name = "Entity Management",
        category_uid = 3,
        category_name = "Identity & Access Management",
        type_uid = 300401,
        time = record.time or (os_time() * 1000)
    }

    -- Safe nested table access helper
    local function get_nested(t, ...)
        local current = t
        for _, key in ipairs({...}) do
            if type(current) ~= "table" then return nil end
            current = current[key]
        end
        return current
    end

    -- Field mappings with validation
    -- Map request.operation -> activity_name and activity_id
    local operation = get_nested(record, "request", "operation")
    if validate_string(operation) then
        output.activity_name = operation
        output.activity_id = ACTIVITY_MAP[operation:lower()] or 1
    end

    -- Map auth.client_token -> unmapped.client_token
    local client_token = get_nested(record, "auth", "client_token")
    if validate_string(client_token) then
        output.unmapped.client_token = client_token
    end

    -- Map request.id -> metadata.uida
    local request_id = get_nested(record, "request", "id")
    if validate_string(request_id) then
        output.metadata.uida = request_id
    end

    -- Map auth.metadata.role -> metadata.role
    local role = get_nested(record, "auth", "metadata", "role")
    if validate_string(role) then
        output.metadata.role = role
    end

    -- Additional field enrichment
    output.metadata.vendor = "HashiCorp"
    output.metadata.product = "HCP Vault"
    
    -- Validation of required fields
    local validation_errors = {}
    if not output.class_uid then
        table_insert(validation_errors, "Missing class_uid")
    end
    if not output.activity_name then
        table_insert(validation_errors, "Missing activity_name")
    end

    if #validation_errors > 0 then
        return nil, string_format("Validation failed: %s", table.concat(validation_errors, ", "))
    end

    return output
end

-- Error handling wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end