-- SentinelOne Parser: tailscale_tailscale_logs-latest 
-- OCSF Class: entity_management (3004) & network_activity (4001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:27:52.986282

-- Pre-compile patterns for performance
local NETWORK_EVENT_PATTERN = "^{\"start.*nodeId.*|^{\"exitTraffic.*"
local CONFIG_EVENT_PATTERN = "^{\"eventGroupID.*"

-- Cached references for performance
local type, pairs, os_time = type, pairs, os.time
local string_match = string.match
local table_insert = table.insert

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record" 
    end

    -- Determine event type and initialize output structure
    local output = {
        metadata = {},
        actor = {user = {}},
        target = {},
        unmapped = {}
    }

    -- Detect event type and set base attributes
    local is_network = record.nodeId ~= nil or record.exitTraffic
    if is_network then
        output.class_uid = 4001
        output.class_name = "network_activity"
        output.category_uid = 4
        output.category_name = "Network Activity"
        output.activity_id = 6
        output.event = {type = "Network Flow"}
        output.severity_id = 1
    else
        output.class_uid = 3004
        output.class_name = "entity_management"
        output.category_uid = 3 
        output.category_name = "Identity & Access Management"
        output.event = {type = "Configuration"}
        output.severity_id = 1
    end

    -- Common field mappings
    output.dataSource = {
        category = "security",
        name = "Tailscale VPN",
        vendor = "Tailscale"
    }

    -- Timestamp handling with validation
    local function set_timestamp(ts_value)
        if type(ts_value) == "number" then
            return ts_value * 1000 -- Convert to milliseconds
        elseif type(ts_value) == "string" then
            -- Basic ISO-8601 timestamp validation
            if string_match(ts_value, "^%d%d%d%d%-%d%d%-%d%dT") then
                return ts_value
            end
        end
        return os_time() * 1000
    end

    -- Network event specific mappings
    if is_network then
        if record.nodeId then
            output.src_endpoint = record.nodeId
            output.event.source = record.nodeId
        end
        
        -- Traffic metadata
        if record.physicalTraffic then
            output.unmapped.physicalTraffic = record.physicalTraffic
        end
        if record.virtualTraffic then
            output.unmapped.virtualTraffic = record.virtualTraffic
        end
        
        -- Timestamps
        output.timestamp = set_timestamp(record.start)
        output.start_time = set_timestamp(record.start)
        output.end_time = set_timestamp(record.end)
        
    -- Config event mappings    
    else
        -- Actor information
        if record.actor then
            if record.actor.displayName then
                output.actor.user.name = record.actor.displayName
            end
            if record.actor.loginName then
                output.actor.user.email_addr = record.actor.loginName
            end
            if record.actor.id then
                output.actor.user.uid = record.actor.id
            end
            if record.actor.type then
                output.actor.user.type = record.actor.type
            end
        end

        -- Target information
        if record.target then
            if record.target.name then
                output.entity.name = record.target.name
            end
            if record.target.id then
                output.target.uid = record.target.id
            end
            if record.target.type then
                output.target.type = record.target.type
            end
        end

        -- Timestamps and metadata
        output.timestamp = set_timestamp(record.new)
        output.start_time = set_timestamp(record.old)
        output.end_time = set_timestamp(record.new)
        
        if record.origin then
            output.metadata.origin = record.origin
        end
    end

    -- Final validation
    if not output.timestamp then
        output.timestamp = os_time() * 1000
    end

    return output
end

-- Error handler wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string.format("Transform error: %s", result)
    end
    return result
end