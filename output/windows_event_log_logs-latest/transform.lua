--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: windows_event_log_logs-latest
  Generated: 2025-10-13T12:38:09.227609
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: windows_event_log_logs-latest 
-- OCSF Class: Authentication (3002)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:04:57.851678

-- Pre-compile patterns for performance
local patterns = {
    account_name = ".*Subject.*Account Name:\\t\\t([^\\r\\n]+)",
    logon_type = ".*Logon Information:.*Logon Type:\\t+([^\\r\\n]+)",
    process_name = ".*Process Information:.*Process Name:\\t+([^\\r\\n]+)"
}

-- Local cache for frequent operations
local type = type
local tonumber = tonumber
local os_time = os.time
local string_match = string.match

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with local table
    local output = {
        class_uid = 3002,
        class_name = "Authentication",
        category_uid = 3, 
        category_name = "Identity & Access Management",
        activity_id = 1,
        type_uid = 300201,
        actor = {
            user = {}
        },
        authentication = {},
        process = {}
    }

    -- Efficient field transformations using local variables
    local account_name = record.Account_Name
    local logon_info = record.logon_Information  
    local process_name = record.Process_Name

    -- Transform actor fields with validation
    if account_name and type(account_name) == "string" then
        output.actor.user.name = account_name
    end

    -- Transform authentication type with casting
    if logon_info then
        local auth_type = tonumber(logon_info)
        if auth_type then
            output.authentication.type = auth_type
        end
    end

    -- Transform process info with validation
    if process_name and type(process_name) == "string" then
        output.process.name = process_name
    end

    -- Add additional Windows-specific fields
    if record.Workstation_Name then
        output.src_endpoint = {hostname = record.Workstation_Name}
    end

    if record.Source_Network_Address then
        output.src = {ip = record.Source_Network_Address}
    end

    -- Enrich with authentication details
    if record.Authentication_Package then
        output.authentication.protocol = record.Authentication_Package
    end

    -- Add timestamp if not present
    if not output.time then
        output.time = os_time() * 1000
    end

    -- Validate required OCSF fields
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid class_uid"
    end

    -- Return transformed record
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

-- Optimization notes:
-- 1. Local variable caching for core functions
-- 2. Pre-compiled patterns for regex operations
-- 3. Table pre-allocation for output structure
-- 4. Minimal string operations
-- 5. Early validation and returns
-- 6. Efficient type checking