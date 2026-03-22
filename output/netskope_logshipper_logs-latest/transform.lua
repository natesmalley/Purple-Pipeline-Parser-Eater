--[[
  SentinelOne to Observo Pipeline Transformation
  Parser ID: netskope_logshipper_logs-latest
  Generated: 2025-10-13T11:43:57.645633
  Generator: Purple Pipeline Parser Eater v9.0.0

  DIRECTOR REQUIREMENT 3: Generated LUA transformation
  Source: SentinelOne AI-SIEM parser
  Target: Observo.ai pipeline
]]

-- SentinelOne Parser: netskope_logshipper_logs-latest 
-- OCSF Class: Security Finding (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T11:10:13.604773

-- Pre-compile patterns for performance
local ipv4_pattern = "^%d+%.%d+%.%d+%.%d+$"
local ipv6_pattern = "^%x+:[%x:]+$"

-- Cached field mappings for performance
local field_mappings = {
  activity = "security_finding.activity_name",
  dlp_incident_id = "dlp.incident_uid", 
  user = "user.email_addr"
}

-- Helper function to safely set nested table fields
local function set_nested_field(tbl, path, value)
  local current = tbl
  local segments = {}
  for segment in path:gmatch("[^%.]+") do
    table.insert(segments, segment)
  end
  
  for i=1, #segments-1 do
    local key = segments[i]
    current[key] = current[key] or {}
    current = current[key]
  end
  current[segments[#segments]] = value
end

function transform(record)
  -- Input validation with detailed error messages
  if not record then
    return nil, "Record is nil"
  end
  
  if type(record) ~= "table" then
    return nil, string.format("Invalid record type: %s", type(record))
  end

  -- Initialize OCSF-compliant output with required fields
  local output = {
    metadata = {
      version = "1.0.0",
      class_uid = 1001,
      class_name = "Security Finding",
      category_uid = 1, 
      category_name = "Security Events"
    },
    security_finding = {},
    dlp = {},
    user = {},
    network_traffic = {},
    location = {}
  }

  -- Process IP addresses with validation
  if record.srcip then
    if record.srcip:match(ipv4_pattern) or record.srcip:match(ipv6_pattern) then
      output.src = {ip = {address = record.srcip}}
    end
  end

  -- Optimized field mapping using cached definitions
  for source_field, target_field in pairs(field_mappings) do
    if record[source_field] then
      set_nested_field(output, target_field, record[source_field])
    end
  end

  -- Handle network traffic fields efficiently
  local traffic_fields = {"client_bytes", "server_bytes", "total_packets"}
  for _, field in ipairs(traffic_fields) do
    if record[field] then
      local num_val = tonumber(record[field])
      if num_val then
        output.network_traffic[field] = num_val
      end
    end
  end

  -- Process location data in batch
  if record.src_country or record.dst_country then
    output.location = {
      src_country = record.src_country,
      dst_country = record.dst_country,
      src_region = record.src_region,
      dst_region = record.dst_region
    }
  end

  -- Add timestamp handling
  output.time = record.timestamp and tonumber(record.timestamp) or os.time() * 1000

  -- Validate required OCSF fields before returning
  if not output.metadata.class_uid then
    return nil, "Missing required class_uid"
  end

  -- Add observability metadata
  output.metadata.parser_version = "1.0.0"
  output.metadata.processing_time = os.time()

  return output
end

-- Error handler wrapper for production use
function safe_transform(record)
  local status, result = pcall(transform, record)
  if not status then
    return nil, string.format("Transform error: %s", result)
  end
  return result
end