--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: inngate_gateway_logs-latest
  Generated: 2025-10-13T11:33:49.024114
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: inngate_gateway_logs-latest 
-- OCSF Class: Network Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T11:05:43.799413

-- Pre-declare locals for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_format = string.format
local ipairs = ipairs

-- Validation helpers
local function is_valid_ip(ip)
    if not ip then return false end
    local parts = {ip:match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")}
    if #parts ~= 4 then return false end
    for _, part in ipairs(parts) do
        local n = tonumber(part)
        if not n or n < 0 or n > 255 then return false end
    end
    return true
end

local function is_valid_mac(mac)
    return mac and mac:match("^%x%x:%x%x:%x%x:%x%x:%x%x:%x%x$") ~= nil
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure with local cache
    local output = {
        class_uid = 1001,
        class_name = "Network Activity",
        category_uid = 1, 
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = 100101,
        metadata = {
            product = {
                name = "InnGate Gateway",
                vendor_name = "InnGate"
            },
            version = "1.0"
        },
        device = {},
        src_endpoint = {},
        dst_endpoint = {},
        http = {}
    }

    -- Optimized field transformations using local references
    local device = output.device
    local src = output.src_endpoint
    local dst = output.dst_endpoint
    local http = output.http

    -- Transform timestamp with validation
    if record.TM then
        local ts = tonumber(record.TM)
        if ts then
            output.time = ts
        end
    end

    -- Transform MAC with validation
    if record.MAC and is_valid_mac(record.MAC) then
        device.mac = record.MAC
    end

    -- Transform IPs with validation
    if record.SA and is_valid_ip(record.SA) then
        src.ip = record.SA
    end

    if record.DA and is_valid_ip(record.DA) then
        dst.ip = record.DA
    end

    -- Transform HTTP method
    if record.METHOD then
        local method = record.METHOD:upper()
        if method:match("^[A-Z]+$") then
            http.method = method
        end
    end

    -- Add additional context fields
    if record.URI then
        http.url = record.URI
    end

    if record.HOST then
        http.host = record.HOST
    end

    -- Enrich with protocol info if available
    if record.PRO then
        output.network = {
            protocol = record.PRO:lower()
        }
    end

    -- Validation and cleanup
    if not output.time then
        output.time = os_time() * 1000
    end

    -- Remove empty tables
    if next(device) == nil then output.device = nil end
    if next(src) == nil then output.src_endpoint = nil end
    if next(dst) == nil then output.dst_endpoint = nil end
    if next(http) == nil then output.http = nil end

    return output
end