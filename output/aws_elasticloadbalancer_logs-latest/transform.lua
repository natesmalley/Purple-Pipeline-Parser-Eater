-- SentinelOne Parser: aws_elasticloadbalancer_logs-latest 
-- OCSF Class: Network Activity (6001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:50:37.422261

-- Pre-declare locals for performance
local type = type
local pairs = pairs
local tonumber = tonumber
local os_time = os.time
local string_format = string.format

-- Validation helper functions
local function validate_ip(ip)
    if not ip then return false end
    local parts = {ip:match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")}
    if #parts ~= 4 then return false end
    for _, part in pairs(parts) do
        local n = tonumber(part)
        if not n or n < 0 or n > 255 then return false end
    end
    return true
end

local function validate_port(port)
    local n = tonumber(port)
    return n and n >= 0 and n <= 65535
end

function transform(record)
    -- Input validation with detailed error messages
    if not record then
        return nil, "Record is nil"
    end
    if type(record) ~= "table" then
        return nil, string_format("Expected table, got %s", type(record))
    end

    -- Initialize output structure with nested tables
    local output = {
        -- OCSF mandatory fields
        class_uid = 6001,
        class_name = "Network Activity",
        category_uid = 6,
        category_name = "Network Activity",
        activity_id = 1,
        type_uid = 600101,
        
        -- Initialize nested structures
        src = {ip = {}},
        dst = {ip = {}},
        network_endpoint = {},
        network_traffic = {},
        access_activity = {}
    }

    -- Optimized field transformations using local references
    local src = output.src.ip
    local dst = output.dst.ip
    local endpoint = output.network_endpoint
    local traffic = output.network_traffic
    local activity = output.access_activity

    -- IP Address handling with validation
    if record.client_ip and validate_ip(record.client_ip) then
        src.address = record.client_ip
    end
    
    if record.backend_ip and validate_ip(record.backend_ip) then
        dst.address = record.backend_ip
    end

    -- Port handling with validation
    if record.client_port and validate_port(record.client_port) then
        endpoint.src_port = tonumber(record.client_port)
    end
    
    if record.backend_port and validate_port(record.backend_port) then
        endpoint.dst_port = tonumber(record.backend_port)
    end

    -- Traffic metrics with type conversion
    if record.received_bytes then
        traffic.bytes_in = tonumber(record.received_bytes) or 0
    end
    
    if record.sent_bytes then
        traffic.bytes_out = tonumber(record.sent_bytes) or 0
    end

    -- Activity timing and status codes
    if record.time then
        activity.response_time = record.time
    end

    if record.alb_status_code then
        activity.load_balancer_status_code = tonumber(record.alb_status_code)
    end

    if record.backend_status_code then
        activity.backend_status_code = tonumber(record.backend_status_code)
    end

    -- Processing times with float conversion
    if record.request_processing_time then
        activity.request_processing_time = tonumber(record.request_processing_time)
    end

    if record.backend_processing_time then
        activity.backend_processing_time = tonumber(record.backend_processing_time)
    end

    if record.response_processing_time then
        activity.response_processing_time = tonumber(record.response_processing_time)
    end

    -- Load balancer name
    if record.alb then
        activity.load_balancer_name = record.alb
    end

    -- Add timestamp if missing
    if not output.time then
        output.time = os_time() * 1000
    end

    -- Final validation
    if not (output.src.ip.address or output.dst.ip.address) then
        return nil, "Missing required IP addresses"
    end

    return output
end