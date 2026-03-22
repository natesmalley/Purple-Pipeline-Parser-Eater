-- SentinelOne Parser: incapsula_incapsula_logs-latest 
-- OCSF Class: Network Activity (4001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:02:17.464584

-- Pre-compile patterns for performance
local PATTERNS = {
    ip = "^%d+%.%d+%.%d+%.%d+$",
    port = "^%d+$",
    url = "^https?://[%w%-%.]+%.[%w%-%.]+",
    http_code = "^%d%d%d$"
}

-- Local cache for frequent operations
local type = type
local tonumber = tonumber
local format = string.format
local match = string.match

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize output structure with nested tables to avoid nil errors
    local output = {
        class_uid = 4001,
        class_name = "Network Activity", 
        category_uid = 4,
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = 400101,
        src = {
            ip = {},
            port = {}
        },
        http_response = {},
        url = {}
    }

    -- Optimized field transformations using local variables
    local src = record.src
    local src_port = record.srcPort
    local http_code = record.cn1 or record.fileId -- Consolidated HTTP code mapping
    local url_addr = record.url

    -- Validate and transform source IP
    if src and match(src, PATTERNS.ip) then
        output.src.ip.address = src
    end

    -- Validate and transform source port 
    if src_port then
        local port_num = tonumber(src_port)
        if port_num and port_num >= 1 and port_num <= 65535 then
            output.src.port.number = port_num
        end
    end

    -- Transform HTTP response code with validation
    if http_code then
        local code_num = tonumber(http_code)
        if code_num and match(tostring(code_num), PATTERNS.http_code) then
            output.http_response.code = code_num
        end
    end

    -- Transform and validate URL
    if url_addr and match(url_addr, PATTERNS.url) then
        output.url.address = url_addr
    end

    -- Add metadata
    output.metadata = {
        version = "1.0.0",
        product = {
            vendor_name = "Imperva",
            name = "Imperva Incapsula"
        }
    }

    -- Add timestamp if not present
    if not output.time then
        output.time = os.time() * 1000
    end

    -- Final validation of required fields
    if not (output.class_uid and output.src.ip.address) then
        return nil, "Missing required fields"
    end

    return output
end

-- Error wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, format("Transform error: %s", result)
    end
    return result
end

-- Optimization notes:
-- 1. Pre-compiled patterns improve regex performance
-- 2. Local variables reduce table lookups
-- 3. Early validation prevents unnecessary processing
-- 4. Consolidated HTTP code mapping reduces redundancy
-- 5. Efficient string matching with pattern caching
-- 6. Nested table initialization prevents nil errors