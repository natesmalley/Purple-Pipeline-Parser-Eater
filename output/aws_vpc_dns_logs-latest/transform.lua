-- SentinelOne Parser: aws_vpc_dns_logs-latest 
-- OCSF Class: DNS Activity (4003)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:51:01.655340

-- Pre-declare locals for performance
local type = type
local tonumber = tonumber
local os_time = os.time
local string_format = string.format
local table_insert = table.insert

-- Validation helper functions
local function validate_ip(ip)
    if not ip then return false end
    local parts = {ip:match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")}
    if #parts ~= 4 then return false end
    for _, part in ipairs(parts) do
        local n = tonumber(part)
        if not n or n < 0 or n > 255 then return false end
    end
    return true
end

local function validate_timestamp(ts)
    local n = tonumber(ts)
    return n and n > 946684800 -- Year 2000
end

function transform(record)
    -- Input validation with early return
    if not record or type(record) ~= "table" then
        return nil, "Invalid input record"
    end

    -- Initialize OCSF-compliant output with constant fields
    local output = {
        activity_id = 6,
        activity_name = "Traffic",
        category_uid = 4,
        category_name = "Network Activity", 
        class_uid = 4003,
        class_name = "DNS Activity",
        type_uid = 400306,
        type_name = "DNS Activity: Traffic",
        metadata = {
            product = {
                name = "VPC DNS",
                vendor_name = "AWS"
            }
        }
    }

    -- Handle timestamp transformation
    if record.query_timestamp then
        if validate_timestamp(record.query_timestamp) then
            output.time = tonumber(record.query_timestamp)
            output.query_time = record.query_timestamp
        else
            output.time = os_time() * 1000
        end
    end

    -- DNS Query fields
    if record.query_name then
        output.query = {
            hostname = record.query_name,
            type = record.query_type,
            class = record.query_class
        }
    end

    -- Source endpoint information
    if record.srcaddr then
        output.src_endpoint = {
            ip = validate_ip(record.srcaddr) and record.srcaddr or nil,
            port = tonumber(record.srcport),
            vpc_uid = record.vpc_id,
            instance_uid = record.srcids and record.srcids.instance
        }
    end

    -- AWS specific fields
    output.cloud = {
        region = record.region,
        account = {
            uid = record.account_id
        }
    }

    -- Handle DNS answers array
    if record.answers and type(record.answers) == "table" then
        output.answers = {}
        for _, answer in ipairs(record.answers) do
            table_insert(output.answers, {
                rdata = answer.Rdata,
                class = answer.Class,
                type = answer.Type
            })
        end
    end

    -- Connection info
    if record.transport then
        output.connection_info = {
            protocol_name = record.transport
        }
    end

    -- Final validation
    if not output.time then
        output.time = os_time() * 1000
    end

    if not output.query or not output.query.hostname then
        return nil, "Missing required DNS query information"
    end

    return output
end