-- SentinelOne Parser: aws_guardduty_logs-latest 
-- OCSF Class: Security Finding (1001)
-- Performance Level: High-volume optimized
-- Generated: 2025-10-13T12:51:00.654178

-- Pre-declare locals for performance
local type = type
local pairs = pairs
local os_time = os.time
local string_format = string.format
local table_insert = table.insert

-- Validation helper functions
local function validate_string(value)
    return type(value) == "string" and #value > 0
end

local function validate_table(value) 
    return type(value) == "table"
end

-- Core transform function
function transform(record)
    -- Input validation with early return
    if not validate_table(record) then
        return nil, "Invalid input record"
    end

    -- Initialize output structure with required OCSF fields
    local output = {
        class_uid = 1001,
        class_name = "Security Finding", 
        category_uid = 1,
        category_name = "Security Events",
        activity_id = 1,
        type_uid = 100101,
        cloud = {},
        finding = {},
        instance_details = {
            cloud = {},
            iam_instance_profile = {},
            image = {},
            instance = {}
        }
    }

    -- Optimized field mapping block
    do
        -- Cloud account mapping
        if validate_string(record.accountId) then
            output.cloud.account_uid = record.accountId
        end

        -- ARN mapping
        if validate_string(record.arn) then
            output.cloud.amazon_resource_name = record.arn
        end

        -- Finding details
        if validate_string(record.createdAt) then
            output.finding.created_time = record.createdAt
        end
        if validate_string(record.description) then
            output.event = {details = record.description}
        end
        if validate_string(record.id) then
            output.finding.uid = record.id
        end

        -- Cloud metadata
        if validate_string(record.partition) then
            output.cloud.partition = record.partition
        end
        if validate_string(record.region) then
            output.cloud.region = record.region
        end

        -- Instance details mapping
        local instance = record.resource and record.resource.instanceDetails
        if validate_table(instance) then
            if validate_string(instance.availabilityZone) then
                output.instance_details.cloud.zone = instance.availabilityZone
            end
            
            -- IAM profile details
            local iam = instance.iamInstanceProfile
            if validate_table(iam) then
                if validate_string(iam.arn) then
                    output.instance_details.iam_instance_profile.amazon_resource_name = iam.arn
                end
                if validate_string(iam.id) then
                    output.instance_details.iam_instance_profile.uid = iam.id
                end
            end

            -- Image details
            if validate_string(instance.imageDescription) then
                output.instance_details.image.desc = instance.imageDescription
            end
            if validate_string(instance.imageId) then
                output.instance_details.image.uid = instance.imageId
            end

            -- Instance state
            if validate_string(instance.instanceId) then
                output.instance_details.instance.uid = instance.instanceId
            end
            if validate_string(instance.instanceState) then
                output.instance_details.instance.state = instance.instanceState
            end
        end
    end

    -- Add timestamp if not present
    if not output.time then
        output.time = os_time() * 1000
    end

    -- Final validation
    if not output.class_uid or output.class_uid == 0 then
        return nil, "Invalid OCSF class_uid"
    end

    return output
end

-- Error wrapper for production use
function safe_transform(record)
    local success, result = pcall(transform, record)
    if not success then
        return nil, string_format("Transform error: %s", result)
    end
    return result
end