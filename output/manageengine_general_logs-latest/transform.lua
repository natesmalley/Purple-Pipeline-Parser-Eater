--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: manageengine_general_logs-latest
  Generated: 2025-10-13T13:05:07.252803
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: manageengine_general_logs-latest 
-- OCSF Class: Account Change (3001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:23:22.839381

-- Pre-compile patterns for performance
local timestamp_pattern = "^(%d%d%d%d%-%d%d%-%d%dT%d%d:%d%d:%d%d)"
local ipv4_pattern = "^(%d+%.%d+%.%d+%.%d+)$"

-- Cached functions for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_match = string.match
local string_format = string.format

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with required fields
    local output = {
        metadata = {
            product = {
                name = "ManageEngine",
                vendor_name = "ManageEngine"
            },
            version = "1.0.0"
        },
        class_uid = 3001,
        class_name = "Account Change",
        category_uid = 3, 
        category_name = "Identity & Access Management",
        severity_id = 2,
        time = nil,
        src_endpoint = {},
        user = {}
    }

    -- Timestamp transformation with validation
    if record.timestamp then
        local parsed_time = string_match(record.timestamp, timestamp_pattern)
        if parsed_time then
            output.time = parsed_time
        else
            output.time = os_time() * 1000 -- Fallback to current time
        end
    end

    -- Source IP transformation with validation
    if record.src_ip then
        local valid_ip = string_match(record.src_ip, ipv4_pattern)
        if valid_ip then
            output.src_endpoint.ip = valid_ip
        end
    end

    -- User transformation
    if record.user then
        output.user.name = record.user
        -- Add user type if available
        if record.user_type then
            output.user.type = record.user_type
        end
    end

    -- Action/activity mapping
    if record.action then
        output.activity_name = record.action
        -- Map common actions to activity IDs
        local activity_map = {
            created = 1,
            modified = 2,
            deleted = 3,
            accessed = 4
        }
        output.activity_id = activity_map[record.action:lower()] or 1
    end

    -- Event type specific handling
    if record.event_type then
        output.type_name = record.event_type
        -- Add to observables if relevant
        if record.event_type:match("security") then
            output.observables = {
                {type = "event_type", value = record.event_type}
            }
        end
    end

    -- Admin user handling for accountability
    if record.admin_user then
        output.actor = {
            user = {
                name = record.admin_user,
                type = "admin"
            }
        }
    end

    -- Method/authentication details
    if record.method then
        output.auth = {
            type = record.method
        }
    end

    -- Status/result mapping
    if record.result then
        output.status = string_format("Operation %s", record.result)
        output.status_id = record.result:lower() == "success" and 1 or 2
    end

    -- Validation of required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    -- Add default timestamp if missing
    if not output.time then
        output.time = os_time() * 1000
    end

    return output
end