-- SentinelOne Parser: darktrace_darktrace_logs-latest 
-- OCSF Class: Security Finding (2001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:58:10.668006

-- Pre-compile patterns for performance
local SEVERITY_PATTERNS = {
    {pattern = "^0$|^0%.1%d+$|^0%.2[0-4]%d*$", value = 2},
    {pattern = "^0%.2[5-9]%d*$|^0%.3%d+$|^0%.4%d+$", value = 3}, 
    {pattern = "^0%.5%d*$|^0%.6%d+$|^0%.7[0-4]%d*$", value = 4},
    {pattern = "^0%.7[5-9]%d*$|^0%.8%d+$|^0%.9%d+$|^1%.%d*$", value = 5}
}

-- Cached field access for performance
local function get_nested_value(record, path)
    local value = record
    for field in string.gmatch(path, "[^%.]+") do
        if type(value) ~= "table" then return nil end
        value = value[field]
    end
    return value
end

-- Calculate severity ID based on score
local function calculate_severity(score)
    if not score then return 3 end -- Default medium severity
    local score_str = tostring(score)
    for _, pattern in ipairs(SEVERITY_PATTERNS) do
        if string.match(score_str, pattern.pattern) then
            return pattern.value
        end
    end
    return 3
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with static fields
    local output = {
        dataSource = {
            category = "security",
            name = "Darktrace",
            vendor = "Darktrace"
        },
        category_name = "Findings",
        category_uid = 2,
        class_name = "Security Finding", 
        class_uid = 2001,
        activity_id = 2,
        status = 200102,
        event = {
            type = "Model Breach"
        }
    }

    -- Efficient field mapping with error handling
    local function safe_map(src_path, dest_path)
        local value = get_nested_value(record, src_path)
        if value then
            local current = output
            local fields = {}
            for field in string.gmatch(dest_path, "[^%.]+") do
                table.insert(fields, field)
            end
            for i=1, #fields-1 do
                current[fields[i]] = current[fields[i]] or {}
                current = current[fields[i]]
            end
            current[fields[#fields]] = value
        end
    end

    -- Core field mappings
    safe_map("time", "timestamp")
    safe_map("creationTime", "finding.created_time")
    safe_map("model.description", "finding.desc")
    safe_map("breachUrl", "finding.src_url")
    safe_map("model.name", "finding.title")
    safe_map("pbid", "finding.uid")
    safe_map("device.hostname", "endpoint.name")
    safe_map("device.ip", "src.ip.address")
    safe_map("triggeredComponents", "evidence")

    -- Handle severity calculation
    local score = get_nested_value(record, "score")
    output.severity_id = calculate_severity(score)

    -- Validation and enrichment
    if not output.timestamp then
        output.timestamp = os.time() * 1000
    end

    -- Required field validation
    if not output.finding or not output.finding.desc then
        return nil, "Missing required field: finding description"
    end

    return output
end

-- Error handling wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string.format("Transform error: %s", result)
    end
    return result
end