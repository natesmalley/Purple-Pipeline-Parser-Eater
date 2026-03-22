-- SentinelOne Parser: linux_auth-latest 
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T13:04:19.181419

-- Pre-declare locals for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_match = string.match
local ipairs = ipairs

-- Validation patterns
local IP_PATTERN = "^%d+%.%d+%.%d+%.%d+$"
local PORT_PATTERN = "^%d+$"

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" or not record.unmapped then
        return nil, "Invalid input record structure"
    end

    -- Initialize OCSF-compliant output with constant fields
    local output = {
        -- Classification
        activity_id = 1,
        activity_name = "Logon",
        category_uid = 3,
        category_name = "Identity & Access Management",
        class_uid = 3002,
        class_name = "Authentication",
        type_uid = 300201,
        type_name = "Authentication: Logon"
    }

    -- Timestamp handling with validation
    local timestamp = record.unmapped.timestamp
    if timestamp then
        local epoch = tonumber(timestamp)
        if epoch then
            output.time = epoch
        else
            output.time = os_time() * 1000
        end
    else
        output.time = os_time() * 1000
    end

    -- Source endpoint processing
    if record.unmapped.hostname then
        output.src_endpoint = output.src_endpoint or {}
        output.src_endpoint.hostname = record.unmapped.hostname
    end

    -- IP validation and assignment
    if record.unmapped.src_ip then
        if string_match(record.unmapped.src_ip, IP_PATTERN) then
            output.src_endpoint = output.src_endpoint or {}
            output.src_endpoint.ip = record.unmapped.src_ip
            
            -- Port validation and assignment
            if record.unmapped.src_port then
                local port = tonumber(record.unmapped.src_port)
                if port and port > 0 and port < 65536 then
                    output.src_endpoint.port = port
                end
            end
        end
    end

    -- Process information
    if record.unmapped.process_name or record.unmapped.process_id then
        output.actor = output.actor or {}
        output.actor.process = output.actor.process or {}
        
        if record.unmapped.process_name then
            output.actor.process.name = record.unmapped.process_name
        end
        
        if record.unmapped.process_id then
            local pid = tonumber(record.unmapped.process_id)
            if pid then
                output.actor.process.pid = pid
            end
        end
    end

    -- User information
    if record.unmapped.username then
        output.user = {
            name = record.unmapped.username
        }
    end

    -- Authentication details
    if record.unmapped.auth_method then
        output.auth_protocol = record.unmapped.auth_method
    end

    -- Status and message
    if record.unmapped.status then
        output.status = record.unmapped.status
    end
    
    if record.unmapped.message then
        output.message = record.unmapped.message
    end

    -- Session handling
    if record.unmapped.session_id then
        output.session = {
            uid = record.unmapped.session_id
        }
    end

    return output
end