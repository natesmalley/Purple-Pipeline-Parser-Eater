-- SentinelOne Parser: buildkite_ci_logs-latest 
-- OCSF Class: Entity Management (3004)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:52:24.123760

-- Pre-compile regex patterns for performance
local email_pattern = "^([^@]+)@(.+)$"

-- Cached activity mappings for performance
local ACTIVITY_MAPPINGS = {
    created = {id = 1, name = "Create", type_uid = 300401},
    added = {id = 1, name = "Create", type_uid = 300401},
    read = {id = 2, name = "Read", type_uid = 300402},
    updated = {id = 3, name = "Update", type_uid = 300403},
    changed = {id = 3, name = "Update", type_uid = 300403},
    deleted = {id = 4, name = "Delete", type_uid = 300404},
    destroyed = {id = 4, name = "Delete", type_uid = 300404},
    removed = {id = 4, name = "Delete", type_uid = 300404},
    enabled = {id = 8, name = "Enable", type_uid = 300408},
    disabled = {id = 9, name = "Disable", type_uid = 300409},
    activated = {id = 10, name = "Activate", type_uid = 300410},
    revoked = {id = 12, name = "Suspend", type_uid = 300412}
}

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with required fields
    local output = {
        class_uid = 3004,
        class_name = "Entity Management",
        category_uid = 3, 
        category_name = "Identity & Access Management",
        severity_id = 99,
        actor = {
            user = {}
        },
        event = {}
    }

    -- Safe access helper function
    local function get_nested(obj, ...)
        local current = obj
        for _, key in ipairs({...}) do
            if type(current) ~= "table" then return nil end
            current = current[key]
        end
        return current
    end

    -- Process unmapped fields efficiently
    if record.unmapped then
        -- Handle event type/action mapping
        local event_type = record.unmapped.type
        if event_type then
            output.event.action = event_type
            
            -- Map activity type
            for pattern, mapping in pairs(ACTIVITY_MAPPINGS) do
                if string.find(event_type, pattern) then
                    output.activity_id = mapping.id
                    output.activity_name = mapping.name
                    output.type_uid = mapping.type_uid
                    output.type_name = string.format("Entity Management: %s", mapping.name)
                    break
                end
            end
        end

        -- Default activity if not matched
        if not output.activity_id then
            output.activity_id = 99
            output.activity_name = "Other"
            output.type_uid = 300499
            output.type_name = "Entity Management: Other"
        end

        -- Handle actor information
        local actor = get_nested(record, "unmapped", "actor")
        if actor then
            if actor.node and actor.node.email then
                output.actor.user.email_addr = actor.node.email
                -- Extract username and domain from email
                local username, domain = string.match(actor.node.email, email_pattern)
                if username and domain then
                    output.actor.user.name = username
                    output.actor.user.domain = domain
                end
            end
            
            output.actor.user.full_name = actor.name
            output.actor.user.uid = actor.uuid
            output.actor.user.type = actor.type
        end

        -- Handle IP address
        local ip = get_nested(record, "unmapped", "context", "requestIpAddress")
        if ip then
            output.src_endpoint = {ip = ip}
        end

        -- Handle timestamp
        local occurred_at = record.unmapped.occurredAt
        if occurred_at then
            -- Convert ISO8601 to epoch seconds
            output.time = tonumber(occurred_at) or os.time()
        else
            output.time = os.time()
        end
    end

    -- Final validation
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    return output
end