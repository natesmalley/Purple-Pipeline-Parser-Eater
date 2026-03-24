--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: sql_database_logs-latest
  Generated: 2025-10-13T11:51:55.281484
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: sql_database_logs-latest 
-- OCSF Class: Database Activity (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T11:13:11.870300

-- Pre-compile patterns for performance
local TIMESTAMP_PATTERN = "^(%d%d%d%d%-%d%d%-%d%d)"
local THREAD_PATTERN = "^%d+ (%d+)"

-- Cache frequently used functions
local tonumber = tonumber
local type = type
local format = string.format
local match = string.match
local time = os.time

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output structure with local vars
    local output = {
        class_uid = 1001,
        class_name = "Database Activity", 
        category_uid = 1,
        category_name = "System Activity",
        activity_id = 1,
        type_uid = 100101,
        metadata = {
            version = "1.0.0",
            product = {
                name = "MySQL Database",
                vendor_name = "MySQL"
            }
        }
    }

    -- Initialize nested objects
    output.process = {}
    output.connection = {}
    
    -- Timestamp transformation with validation
    if record.timestamp then
        local ts = match(record.timestamp, TIMESTAMP_PATTERN)
        if ts then
            output.time = ts
        else
            output.time = time() * 1000 -- Fallback to current time
        end
    end

    -- Thread ID transformation with type safety
    if record.thread_id then
        local thread_num = tonumber(record.thread_id)
        if thread_num then
            output.process.pid = thread_num
        end
    end

    -- Command transformation with sanitization
    if record.command then
        output.activity_name = record.command
        -- Map common commands to OCSF activity types
        local command_map = {
            ["Connect"] = "database_connect",
            ["Quit"] = "database_disconnect",
            ["Init"] = "database_init"
        }
        output.activity_type = command_map[record.command] or "database_query"
    end

    -- Connection info transformation with validation
    if record.connection then
        if type(record.connection) == "string" then
            output.connection.protocol = record.protocol or "TCP"
            output.connection.src = record.connection
        end
    end

    -- Database context
    if record.Database then
        output.database = {
            name = record.Database
        }
    end

    -- Query body handling with size limits
    if record["body-full"] then
        local query = record["body-full"]
        if #query > 4096 then -- Prevent oversized queries
            query = string.sub(query, 1, 4096) .. "..."
        end
        output.query = query
    end

    -- Validation of required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    -- Ensure timestamp exists
    if not output.time then
        output.time = time() * 1000
    end

    return output
end

-- Error handler wrapper
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, format("Transform error: %s", result)
    end
    return result
end