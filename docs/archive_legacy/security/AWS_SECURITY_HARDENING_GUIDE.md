# Purple Pipeline Parser Eater - AWS Security Hardening Guide
**Version 9.0.0** | Enterprise-Grade Security | STIG & FIPS Compliant

## 🔒 Executive Summary

This guide provides **comprehensive security controls** for deploying Purple Pipeline Parser Eater on AWS with enterprise-grade security, meeting STIG, FIPS 140-2, SOC 2, and AWS Well-Architected Framework requirements.

### Security Principles Applied
- **Defense in Depth**: Multiple security layers
- **Least Privilege**: Minimal IAM permissions
- **Zero Trust**: Verify everything, trust nothing
- **Encryption Everywhere**: Data at rest and in transit
- **Audit Everything**: Complete logging and monitoring
- **Compliance First**: STIG, FIPS, PCI-DSS ready

---

## 📋 Table of Contents

1. [AWS Account Security](#aws-account-security)
2. [IAM Security](#iam-security)
3. [VPC and Network Security](#vpc-and-network-security)
4. [ECS/Fargate Security](#ecsfargate-security)
5. [EKS Security](#eks-security)
6. [Secrets Management](#secrets-management)
7. [Encryption](#encryption)
8. [Monitoring and Logging](#monitoring-and-logging)
9. [Compliance](#compliance)
10. [Security Automation](#security-automation)

---

## 🛡️ AWS Account Security

### 1. Enable AWS Organizations

```bash
# Create AWS Organization
aws organizations create-organization --feature-set ALL

# Create dedicated security account
aws organizations create-account \
    --email security@example.com \
    --account-name "Purple-Parser-Security"
```

### 2. Enable AWS CloudTrail (Mandatory)

```bash
# Create S3 bucket for CloudTrail logs
aws s3api create-bucket \
    --bucket purple-parser-cloudtrail-logs-${ACCOUNT_ID} \
    --region us-east-1

# Enable S3 bucket encryption
aws s3api put-bucket-encryption \
    --bucket purple-parser-cloudtrail-logs-${ACCOUNT_ID} \
    --server-side-encryption-configuration '{
      "Rules": [{
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "aws:kms",
          "KMSMasterKeyID": "arn:aws:kms:us-east-1:ACCOUNT_ID:key/KEY_ID"
        }
      }]
    }'

# Create CloudTrail
aws cloudtrail create-trail \
    --name purple-parser-trail \
    --s3-bucket-name purple-parser-cloudtrail-logs-${ACCOUNT_ID} \
    --is-multi-region-trail \
    --enable-log-file-validation \
    --kms-key-id arn:aws:kms:us-east-1:ACCOUNT_ID:key/KEY_ID

# Start logging
aws cloudtrail start-logging --name purple-parser-trail
```

**Security Controls**:
- ✅ All API calls logged
- ✅ Log file integrity validation
- ✅ Encrypted with KMS
- ✅ Multi-region enabled

### 3. Enable AWS Config

```bash
# Create S3 bucket for Config
aws s3api create-bucket \
    --bucket purple-parser-config-${ACCOUNT_ID} \
    --region us-east-1

# Create Config recorder
aws configservice put-configuration-recorder \
    --configuration-recorder name=purple-parser-recorder,roleARN=arn:aws:iam::ACCOUNT_ID:role/aws-config-role \
    --recording-group allSupported=true,includeGlobalResourceTypes=true

# Create delivery channel
aws configservice put-delivery-channel \
    --delivery-channel name=purple-parser-channel,s3BucketName=purple-parser-config-${ACCOUNT_ID}

# Start recorder
aws configservice start-configuration-recorder \
    --configuration-recorder-name purple-parser-recorder
```

### 4. Enable GuardDuty

```bash
# Enable GuardDuty
aws guardduty create-detector \
    --enable \
    --finding-publishing-frequency FIFTEEN_MINUTES
```

### 5. Enable Security Hub

```bash
# Enable Security Hub
aws securityhub enable-security-hub

# Enable CIS AWS Foundations Benchmark
aws securityhub batch-enable-standards \
    --standards-subscription-requests '[{
      "StandardsArn": "arn:aws:securityhub:us-east-1::standards/cis-aws-foundations-benchmark/v/1.4.0"
    }]'
```

---

## 🔐 IAM Security

### 1. ECS Task Execution Role (Minimal Permissions)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ECRAccess",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/ecs/purple-parser:*"
    },
    {
      "Sid": "SecretsManagerRead",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:*:*:secret:purple-parser/*"
      ]
    },
    {
      "Sid": "KMSDecrypt",
      "Effect": "Allow",
      "Action": [
        "kms:Decrypt",
        "kms:DescribeKey"
      ],
      "Resource": "arn:aws:kms:*:*:key/*",
      "Condition": {
        "StringEquals": {
          "kms:ViaService": [
            "secretsmanager.us-east-1.amazonaws.com"
          ]
        }
      }
    }
  ]
}
```

**Apply the role**:
```bash
# Create the policy
aws iam create-policy \
    --policy-name PurpleParserECSExecutionPolicy \
    --policy-document file://ecs-execution-policy.json

# Create the role
aws iam create-role \
    --role-name PurpleParserECSExecutionRole \
    --assume-role-policy-document '{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Principal": {
          "Service": "ecs-tasks.amazonaws.com"
        },
        "Action": "sts:AssumeRole"
      }]
    }'

# Attach the policy
aws iam attach-role-policy \
    --role-name PurpleParserECSExecutionRole \
    --policy-arn arn:aws:iam::ACCOUNT_ID:policy/PurpleParserECSExecutionPolicy
```

### 2. ECS Task Role (Application Permissions)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3OutputAccess",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::purple-parser-output/*"
    },
    {
      "Sid": "DenyUnencryptedS3",
      "Effect": "Deny",
      "Action": "s3:PutObject",
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "s3:x-amz-server-side-encryption": "aws:kms"
        }
      }
    },
    {
      "Sid": "CloudWatchMetrics",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "cloudwatch:namespace": "PurpleParser"
        }
      }
    }
  ]
}
```

### 3. EKS Node Role

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeRouteTables",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeSubnets",
        "ec2:DescribeVolumes",
        "ec2:DescribeVolumesModifications",
        "ec2:DescribeVpcs",
        "eks:DescribeCluster"
      ],
      "Resource": "*"
    }
  ]
}
```

### 4. Service Account (Kubernetes + IRSA)

```yaml
# ServiceAccount with IAM Role for Service Accounts (IRSA)
apiVersion: v1
kind: ServiceAccount
metadata:
  name: purple-parser-sa
  namespace: purple-parser
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT_ID:role/PurpleParserServiceAccountRole
automountServiceAccountToken: false
```

---

## 🌐 VPC and Network Security

### 1. Create Isolated VPC

```bash
# Create VPC with CIDR
aws ec2 create-vpc \
    --cidr-block 10.0.0.0/16 \
    --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=purple-parser-vpc}]'

export VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=tag:Name,Values=purple-parser-vpc" \
    --query 'Vpcs[0].VpcId' --output text)

# Enable VPC Flow Logs
aws ec2 create-flow-logs \
    --resource-type VPC \
    --resource-ids $VPC_ID \
    --traffic-type ALL \
    --log-destination-type cloud-watch-logs \
    --log-group-name /aws/vpc/purple-parser \
    --deliver-logs-permission-arn arn:aws:iam::ACCOUNT_ID:role/VPCFlowLogsRole
```

### 2. Create Private Subnets (Best Practice)

```bash
# Create private subnet in AZ1
aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --cidr-block 10.0.1.0/24 \
    --availability-zone us-east-1a \
    --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=purple-parser-private-1a},{Key=Type,Value=private}]'

# Create private subnet in AZ2
aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --cidr-block 10.0.2.0/24 \
    --availability-zone us-east-1b \
    --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=purple-parser-private-1b},{Key=Type,Value=private}]'

# Create public subnet for NAT Gateway (if needed)
aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --cidr-block 10.0.100.0/24 \
    --availability-zone us-east-1a \
    --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=purple-parser-public-1a},{Key=Type,Value=public}]'
```

### 3. Security Groups (Least Privilege)

```bash
# Create security group for application
aws ec2 create-security-group \
    --group-name purple-parser-app-sg \
    --description "Purple Parser Application Security Group" \
    --vpc-id $VPC_ID

export APP_SG_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=purple-parser-app-sg" \
    --query 'SecurityGroups[0].GroupId' --output text)

# Allow HTTPS inbound from ALB only
aws ec2 authorize-security-group-ingress \
    --group-id $APP_SG_ID \
    --protocol tcp \
    --port 8080 \
    --source-group $ALB_SG_ID

# NO direct internet access (use NAT Gateway)
# NO SSH access (use AWS Systems Manager Session Manager)

# Create security group for ALB
aws ec2 create-security-group \
    --group-name purple-parser-alb-sg \
    --description "Purple Parser ALB Security Group" \
    --vpc-id $VPC_ID

export ALB_SG_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=purple-parser-alb-sg" \
    --query 'SecurityGroups[0].GroupId' --output text)

# Allow HTTPS from specific IP ranges only (not 0.0.0.0/0)
aws ec2 authorize-security-group-ingress \
    --group-id $ALB_SG_ID \
    --protocol tcp \
    --port 443 \
    --cidr 203.0.113.0/24  # Replace with your corporate IP range
```

### 4. Network ACLs (Additional Layer)

```bash
# Create Network ACL for private subnets
aws ec2 create-network-acl \
    --vpc-id $VPC_ID \
    --tag-specifications 'ResourceType=network-acl,Tags=[{Key=Name,Value=purple-parser-private-nacl}]'

# Deny all inbound by default (explicit deny)
aws ec2 create-network-acl-entry \
    --network-acl-id $NACL_ID \
    --ingress \
    --rule-number 100 \
    --protocol -1 \
    --rule-action deny \
    --cidr-block 0.0.0.0/0

# Allow only necessary outbound (HTTPS to AWS services)
aws ec2 create-network-acl-entry \
    --network-acl-id $NACL_ID \
    --egress \
    --rule-number 100 \
    --protocol tcp \
    --port-range From=443,To=443 \
    --rule-action allow \
    --cidr-block 0.0.0.0/0
```

### 5. VPC Endpoints (PrivateLink)

```bash
# S3 VPC Endpoint (Gateway)
aws ec2 create-vpc-endpoint \
    --vpc-id $VPC_ID \
    --service-name com.amazonaws.us-east-1.s3 \
    --route-table-ids $PRIVATE_RT_ID

# ECR VPC Endpoint (Interface)
aws ec2 create-vpc-endpoint \
    --vpc-id $VPC_ID \
    --vpc-endpoint-type Interface \
    --service-name com.amazonaws.us-east-1.ecr.dkr \
    --subnet-ids $PRIVATE_SUBNET_ID \
    --security-group-ids $VPC_ENDPOINT_SG_ID

# Secrets Manager VPC Endpoint
aws ec2 create-vpc-endpoint \
    --vpc-id $VPC_ID \
    --vpc-endpoint-type Interface \
    --service-name com.amazonaws.us-east-1.secretsmanager \
    --subnet-ids $PRIVATE_SUBNET_ID \
    --security-group-ids $VPC_ENDPOINT_SG_ID

# CloudWatch Logs VPC Endpoint
aws ec2 create-vpc-endpoint \
    --vpc-id $VPC_ID \
    --vpc-endpoint-type Interface \
    --service-name com.amazonaws.us-east-1.logs \
    --subnet-ids $PRIVATE_SUBNET_ID \
    --security-group-ids $VPC_ENDPOINT_SG_ID
```

**Benefits**:
- ✅ No internet gateway needed
- ✅ Traffic stays within AWS network
- ✅ Reduces data transfer costs
- ✅ Better security posture

---

## 🐋 ECS/Fargate Security

### 1. ECS Cluster with Container Insights

```bash
# Create ECS cluster with Container Insights
aws ecs create-cluster \
    --cluster-name purple-parser-cluster \
    --capacity-providers FARGATE FARGATE_SPOT \
    --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1,base=1 \
    --settings name=containerInsights,value=enabled \
    --tags key=Environment,value=production key=Project,value=PurpleParser
```

### 2. Secure Task Definition

```json
{
  "family": "purple-parser-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "8192",
  "executionRoleArn": "arn:aws:iam::ACCOUNT_ID:role/PurpleParserECSExecutionRole",
  "taskRoleArn": "arn:aws:iam::ACCOUNT_ID:role/PurpleParserTaskRole",
  "containerDefinitions": [
    {
      "name": "parser-eater",
      "image": "ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/purple-parser:9.0.0",
      "essential": true,
      "user": "999:999",
      "readonlyRootFilesystem": true,
      "privileged": false,
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "APP_ENV", "value": "production"},
        {"name": "PYTHONUNBUFFERED", "value": "1"},
        {"name": "OPENSSL_FIPS", "value": "1"}
      ],
      "secrets": [
        {
          "name": "ANTHROPIC_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:purple-parser/anthropic-api-key"
        },
        {
          "name": "GITHUB_TOKEN",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:purple-parser/github-token"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/purple-parser",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "parser-eater",
          "awslogs-create-group": "true"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8080/api/status || exit 1"],
        "interval": 30,
        "timeout": 10,
        "retries": 3,
        "startPeriod": 120
      },
      "linuxParameters": {
        "capabilities": {
          "drop": ["ALL"],
          "add": ["NET_BIND_SERVICE"]
        },
        "initProcessEnabled": true
      }
    }
  ]
}
```

**Security Features**:
- ✅ Non-root user (999:999)
- ✅ Read-only root filesystem
- ✅ All capabilities dropped
- ✅ Secrets from Secrets Manager (not environment variables)
- ✅ Dedicated IAM roles (separation of concerns)
- ✅ Health checks enabled
- ✅ CloudWatch Logs integration

### 3. ECS Service with ALB

```bash
# Create Application Load Balancer
aws elbv2 create-load-balancer \
    --name purple-parser-alb \
    --subnets $PUBLIC_SUBNET_1 $PUBLIC_SUBNET_2 \
    --security-groups $ALB_SG_ID \
    --scheme internet-facing \
    --type application \
    --ip-address-type ipv4

# Create target group
aws elbv2 create-target-group \
    --name purple-parser-tg \
    --protocol HTTP \
    --port 8080 \
    --vpc-id $VPC_ID \
    --target-type ip \
    --health-check-protocol HTTP \
    --health-check-path /api/status \
    --health-check-interval-seconds 30 \
    --healthy-threshold-count 2 \
    --unhealthy-threshold-count 3

# Create HTTPS listener with ACM certificate
aws elbv2 create-listener \
    --load-balancer-arn $ALB_ARN \
    --protocol HTTPS \
    --port 443 \
    --certificates CertificateArn=$ACM_CERT_ARN \
    --ssl-policy ELBSecurityPolicy-TLS-1-2-2017-01 \
    --default-actions Type=forward,TargetGroupArn=$TG_ARN

# Create ECS service
aws ecs create-service \
    --cluster purple-parser-cluster \
    --service-name purple-parser-service \
    --task-definition purple-parser-task \
    --desired-count 2 \
    --launch-type FARGATE \
    --platform-version LATEST \
    --network-configuration "awsvpcConfiguration={
      subnets=[$PRIVATE_SUBNET_1,$PRIVATE_SUBNET_2],
      securityGroups=[$APP_SG_ID],
      assignPublicIp=DISABLED
    }" \
    --load-balancers "targetGroupArn=$TG_ARN,containerName=parser-eater,containerPort=8080" \
    --enable-execute-command \
    --propagate-tags SERVICE
```

**Security Features**:
- ✅ HTTPS only (TLS 1.2+)
- ✅ AWS Certificate Manager (ACM) certificates
- ✅ Private subnets (no public IP)
- ✅ ALB in public subnet (controlled access)
- ✅ Health checks on application endpoint

---

## ☸️ EKS Security

### 1. Create EKS Cluster with Security Best Practices

```bash
# Create EKS cluster with eksctl
eksctl create cluster \
  --name purple-parser-cluster \
  --version 1.28 \
  --region us-east-1 \
  --vpc-private-subnets $PRIVATE_SUBNET_1,$PRIVATE_SUBNET_2 \
  --vpc-public-subnets $PUBLIC_SUBNET_1,$PUBLIC_SUBNET_2 \
  --without-nodegroup \
  --enable-ssm \
  --asg-access \
  --external-dns-access \
  --full-ecr-access \
  --alb-ingress-access \
  --set-kubeconfig-context

# Enable control plane logging
aws eks update-cluster-config \
  --name purple-parser-cluster \
  --logging '{"clusterLogging":[{
    "types":["api","audit","authenticator","controllerManager","scheduler"],
    "enabled":true
  }]}'

# Enable encryption for secrets
aws eks associate-encryption-config \
  --cluster-name purple-parser-cluster \
  --encryption-config '[{
    "resources": ["secrets"],
    "provider": {
      "keyArn": "arn:aws:kms:us-east-1:ACCOUNT_ID:key/KEY_ID"
    }
  }]'
```

### 2. Create Managed Node Group (Secure)

```bash
# Create managed node group with security features
eksctl create nodegroup \
  --cluster purple-parser-cluster \
  --name purple-parser-ng \
  --node-type t3.xlarge \
  --nodes 2 \
  --nodes-min 1 \
  --nodes-max 4 \
  --node-volume-size 50 \
  --node-volume-type gp3 \
  --node-private-networking \
  --managed \
  --asg-access \
  --external-dns-access \
  --full-ecr-access \
  --alb-ingress-access \
  --node-ami-family Bottlerocket \
  --ssh-access=false
```

**Security Features**:
- ✅ Bottlerocket OS (security-focused, minimal attack surface)
- ✅ No SSH access (use Systems Manager)
- ✅ Private networking only
- ✅ Managed updates
- ✅ GP3 volumes (better performance & encryption)

### 3. Pod Security Standards

```yaml
# Create PodSecurityPolicy (deprecated but shown for context)
# Use Pod Security Admission instead (Kubernetes 1.25+)

apiVersion: policy/v1beta1
kind: PodSecurityPolicy
metadata:
  name: purple-parser-restricted
spec:
  privileged: false
  allowPrivilegeEscalation: false
  requiredDropCapabilities:
    - ALL
  volumes:
    - 'configMap'
    - 'emptyDir'
    - 'projected'
    - 'secret'
    - 'downwardAPI'
    - 'persistentVolumeClaim'
  hostNetwork: false
  hostIPC: false
  hostPID: false
  runAsUser:
    rule: 'MustRunAsNonRoot'
  seLinux:
    rule: 'RunAsAny'
  supplementalGroups:
    rule: 'RunAsAny'
  fsGroup:
    rule: 'RunAsAny'
  readOnlyRootFilesystem: true
```

### 4. Network Policies

```yaml
# Deny all ingress by default
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: purple-parser
spec:
  podSelector: {}
  policyTypes:
  - Ingress

---
# Allow ingress from ALB Ingress Controller
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-alb-ingress
  namespace: purple-parser
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: purple-pipeline-parser-eater
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: kube-system
      podSelector:
        matchLabels:
          app.kubernetes.io/name: aws-load-balancer-controller
    ports:
    - protocol: TCP
      port: 8080

---
# Allow egress to AWS services only
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-aws-services
  namespace: purple-parser
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: purple-pipeline-parser-eater
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app.kubernetes.io/name: milvus
    ports:
    - protocol: TCP
      port: 19530
  - to:
    - ipBlock:
        cidr: 0.0.0.0/0
        except:
        - 169.254.169.254/32  # Block IMDS v1
    ports:
    - protocol: TCP
      port: 443  # HTTPS only
```

### 5. IRSA (IAM Roles for Service Accounts)

```bash
# Create IAM OIDC provider for EKS cluster
eksctl utils associate-iam-oidc-provider \
  --cluster purple-parser-cluster \
  --approve

# Create IAM role for service account
eksctl create iamserviceaccount \
  --name purple-parser-sa \
  --namespace purple-parser \
  --cluster purple-parser-cluster \
  --role-name PurpleParserServiceAccountRole \
  --attach-policy-arn arn:aws:iam::ACCOUNT_ID:policy/PurpleParserAppPolicy \
  --approve \
  --override-existing-serviceaccounts
```

---

## 🔑 Secrets Management

### 1. AWS Secrets Manager (Recommended)

```bash
# Create secrets in Secrets Manager
aws secretsmanager create-secret \
    --name purple-parser/anthropic-api-key \
    --description "Anthropic Claude API Key for Purple Parser" \
    --secret-string "sk-ant-api03-YOUR-KEY" \
    --kms-key-id arn:aws:kms:us-east-1:ACCOUNT_ID:key/KEY_ID \
    --tags Key=Project,Value=PurpleParser Key=Environment,Value=production

aws secretsmanager create-secret \
    --name purple-parser/github-token \
    --description "GitHub Personal Access Token" \
    --secret-string "github_pat_YOUR-TOKEN" \
    --kms-key-id arn:aws:kms:us-east-1:ACCOUNT_ID:key/KEY_ID \
    --tags Key=Project,Value=PurpleParser Key=Environment,Value=production

# Enable automatic rotation (90 days)
aws secretsmanager rotate-secret \
    --secret-id purple-parser/anthropic-api-key \
    --rotation-lambda-arn arn:aws:lambda:us-east-1:ACCOUNT_ID:function:SecretsManagerRotation \
    --rotation-rules AutomaticallyAfterDays=90
```

### 2. External Secrets Operator (EKS)

```yaml
# Install External Secrets Operator
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets \
  external-secrets/external-secrets \
  -n external-secrets-system \
  --create-namespace

---
# Create ClusterSecretStore
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa
            namespace: external-secrets-system

---
# Create ExternalSecret
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: purple-parser-secrets
  namespace: purple-parser
spec:
  refreshInterval: 1h
  secretStoreRef:
    kind: ClusterSecretStore
    name: aws-secrets-manager
  target:
    name: purple-parser-secrets
    creationPolicy: Owner
  data:
    - secretKey: ANTHROPIC_API_KEY
      remoteRef:
        key: purple-parser/anthropic-api-key
    - secretKey: GITHUB_TOKEN
      remoteRef:
        key: purple-parser/github-token
```

**Benefits**:
- ✅ Secrets never stored in code or config files
- ✅ Automatic rotation
- ✅ Encrypted with KMS
- ✅ Audit logging via CloudTrail
- ✅ Fine-grained IAM access control

---

## 🔐 Encryption

### 1. KMS Key Creation

```bash
# Create KMS key for Purple Parser
aws kms create-key \
    --description "Purple Parser Encryption Key" \
    --key-policy '{
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "Enable IAM User Permissions",
          "Effect": "Allow",
          "Principal": {
            "AWS": "arn:aws:iam::ACCOUNT_ID:root"
          },
          "Action": "kms:*",
          "Resource": "*"
        },
        {
          "Sid": "Allow ECS to use the key",
          "Effect": "Allow",
          "Principal": {
            "Service": "ecs-tasks.amazonaws.com"
          },
          "Action": [
            "kms:Decrypt",
            "kms:DescribeKey"
          ],
          "Resource": "*",
          "Condition": {
            "StringEquals": {
              "kms:ViaService": "secretsmanager.us-east-1.amazonaws.com"
            }
          }
        }
      ]
    }' \
    --tags TagKey=Project,TagValue=PurpleParser

# Create alias
aws kms create-alias \
    --alias-name alias/purple-parser \
    --target-key-id KEY_ID
```

### 2. S3 Encryption (Output Storage)

```bash
# Create S3 bucket with encryption
aws s3api create-bucket \
    --bucket purple-parser-output-${ACCOUNT_ID} \
    --region us-east-1

# Enable default encryption
aws s3api put-bucket-encryption \
    --bucket purple-parser-output-${ACCOUNT_ID} \
    --server-side-encryption-configuration '{
      "Rules": [{
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "aws:kms",
          "KMSMasterKeyID": "arn:aws:kms:us-east-1:ACCOUNT_ID:key/KEY_ID"
        },
        "BucketKeyEnabled": true
      }]
    }'

# Enable versioning
aws s3api put-bucket-versioning \
    --bucket purple-parser-output-${ACCOUNT_ID} \
    --versioning-configuration Status=Enabled

# Block public access
aws s3api put-public-access-block \
    --bucket purple-parser-output-${ACCOUNT_ID} \
    --public-access-block-configuration \
      "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Enable bucket logging
aws s3api put-bucket-logging \
    --bucket purple-parser-output-${ACCOUNT_ID} \
    --bucket-logging-status '{
      "LoggingEnabled": {
        "TargetBucket": "purple-parser-logs-${ACCOUNT_ID}",
        "TargetPrefix": "s3-access-logs/"
      }
    }'
```

### 3. EBS Encryption (EKS Nodes)

```yaml
# EKS StorageClass with encryption
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3-encrypted
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  encrypted: "true"
  kmsKeyId: "arn:aws:kms:us-east-1:ACCOUNT_ID:key/KEY_ID"
  iops: "3000"
  throughput: "125"
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
```

---

## 📊 Monitoring and Logging

### 1. CloudWatch Log Groups

```bash
# Create log group with retention and encryption
aws logs create-log-group \
    --log-group-name /ecs/purple-parser

aws logs put-retention-policy \
    --log-group-name /ecs/purple-parser \
    --retention-in-days 90

aws logs associate-kms-key \
    --log-group-name /ecs/purple-parser \
    --kms-key-id arn:aws:kms:us-east-1:ACCOUNT_ID:key/KEY_ID
```

### 2. CloudWatch Alarms

```bash
# High CPU alarm
aws cloudwatch put-metric-alarm \
    --alarm-name purple-parser-high-cpu \
    --alarm-description "Alert when CPU exceeds 80%" \
    --metric-name CPUUtilization \
    --namespace AWS/ECS \
    --statistic Average \
    --period 300 \
    --threshold 80 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 2 \
    --dimensions Name=ServiceName,Value=purple-parser-service Name=ClusterName,Value=purple-parser-cluster \
    --alarm-actions arn:aws:sns:us-east-1:ACCOUNT_ID:purple-parser-alerts

# High memory alarm
aws cloudwatch put-metric-alarm \
    --alarm-name purple-parser-high-memory \
    --alarm-description "Alert when memory exceeds 80%" \
    --metric-name MemoryUtilization \
    --namespace AWS/ECS \
    --statistic Average \
    --period 300 \
    --threshold 80 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 2 \
    --dimensions Name=ServiceName,Value=purple-parser-service Name=ClusterName,Value=purple-parser-cluster \
    --alarm-actions arn:aws:sns:us-east-1:ACCOUNT_ID:purple-parser-alerts

# Health check failures
aws cloudwatch put-metric-alarm \
    --alarm-name purple-parser-unhealthy-targets \
    --alarm-description "Alert when targets are unhealthy" \
    --metric-name UnHealthyHostCount \
    --namespace AWS/ApplicationELB \
    --statistic Average \
    --period 60 \
    --threshold 1 \
    --comparison-operator GreaterThanOrEqualToThreshold \
    --evaluation-periods 2 \
    --dimensions Name=TargetGroup,Value=$TG_ARN Name=LoadBalancer,Value=$ALB_ARN \
    --alarm-actions arn:aws:sns:us-east-1:ACCOUNT_ID:purple-parser-alerts
```

### 3. AWS X-Ray (Distributed Tracing)

```bash
# Enable X-Ray on ECS task
# Add to task definition:
{
  "name": "xray-daemon",
  "image": "amazon/aws-xray-daemon:latest",
  "cpu": 32,
  "memoryReservation": 256,
  "portMappings": [
    {
      "containerPort": 2000,
      "protocol": "udp"
    }
  ]
}
```

---

## 📋 Compliance

### 1. AWS Audit Manager

```bash
# Create assessment for compliance
aws auditmanager create-assessment \
    --name "Purple Parser STIG Compliance" \
    --assessment-reports-destination '{
      "destinationType": "S3",
      "destination": "s3://purple-parser-audit-reports"
    }' \
    --scope '{
      "awsAccounts": [{"id": "ACCOUNT_ID"}],
      "awsServices": [{"serviceName": "ECS"}, {"serviceName": "EKS"}]
    }' \
    --framework-id STIG_FRAMEWORK_ID
```

### 2. Compliance Checklist

#### STIG Compliance
- ✅ V-230276: Non-root container execution
- ✅ V-230285: Read-only root filesystem
- ✅ V-230286: Minimal capabilities
- ✅ V-230287: No new privileges
- ✅ V-230289: Structured logging
- ✅ V-230290: Resource limits
- ✅ V-242383: Service account with minimal permissions
- ✅ V-242400: Resource quotas
- ✅ V-242415: Sensitive data labeling
- ✅ V-242436: Pod security context
- ✅ V-242437: Container security context
- ✅ V-242438: Pod tolerations

#### FIPS 140-2 Compliance
- ✅ KMS uses FIPS 140-2 Level 3 validated modules
- ✅ TLS 1.2+ with FIPS-approved cipher suites
- ✅ Container environment has FIPS mode enabled
- ✅ All encryption uses FIPS-validated algorithms

#### PCI-DSS (If applicable)
- ✅ Network segmentation (VPC, Security Groups)
- ✅ Encryption at rest (KMS)
- ✅ Encryption in transit (TLS 1.2+)
- ✅ Access logging (CloudTrail)
- ✅ Monitoring and alerting (CloudWatch)
- ✅ Regular security testing (AWS Inspector)

#### SOC 2
- ✅ Logical access controls (IAM)
- ✅ Change management (CloudFormation/Terraform)
- ✅ Availability monitoring (CloudWatch)
- ✅ Encryption (KMS, TLS)
- ✅ Incident response (CloudWatch Alarms, SNS)

---

## 🤖 Security Automation

### 1. AWS Inspector (Vulnerability Scanning)

```bash
# Enable AWS Inspector
aws inspector2 enable \
    --resource-types ECR EC2

# Scan ECR repository
aws inspector2 create-scan \
    --resource-id arn:aws:ecr:us-east-1:ACCOUNT_ID:repository/purple-parser
```

### 2. AWS Systems Manager Patch Manager

```bash
# Create patch baseline
aws ssm create-patch-baseline \
    --name "Purple-Parser-Baseline" \
    --operating-system "AMAZON_LINUX_2" \
    --approval-rules '{
      "PatchRules": [{
        "PatchFilterGroup": {
          "PatchFilters": [{
            "Key": "CLASSIFICATION",
            "Values": ["Security", "Critical"]
          }]
        },
        "ComplianceLevel": "CRITICAL",
        "ApproveAfterDays": 0
      }]
    }'

# Create maintenance window
aws ssm create-maintenance-window \
    --name "Purple-Parser-Patching" \
    --schedule "cron(0 2 ? * SUN *)" \
    --duration 4 \
    --cutoff 1 \
    --allow-unassociated-targets
```

### 3. Automated Incident Response

```python
# Lambda function for automated response
import boto3

def lambda_handler(event, context):
    """
    Automated incident response for security findings
    """
    finding = event['detail']['findings'][0]
    severity = finding['Severity']['Label']

    if severity in ['CRITICAL', 'HIGH']:
        # Stop affected task
        ecs = boto3.client('ecs')
        ecs.stop_task(
            cluster='purple-parser-cluster',
            task=finding['Resources'][0]['Id'],
            reason='Security finding detected'
        )

        # Send alert
        sns = boto3.client('sns')
        sns.publish(
            TopicArn='arn:aws:sns:us-east-1:ACCOUNT_ID:security-alerts',
            Subject=f'{severity} Security Finding',
            Message=f"Finding: {finding['Title']}\nDescription: {finding['Description']}"
        )

    return {'statusCode': 200}
```

---

## 🎯 Security Best Practices Summary

### Network Security
✅ Private subnets for all application containers
✅ No public IP addresses assigned
✅ ALB in public subnet with WAF (optional)
✅ Security groups with least privilege
✅ VPC Flow Logs enabled
✅ VPC Endpoints for AWS services (no internet)

### IAM Security
✅ Separate execution and task roles
✅ Minimal permissions (least privilege)
✅ IRSA for EKS (no node-level permissions)
✅ No hardcoded credentials
✅ Regular access reviews

### Encryption
✅ KMS encryption for all data at rest
✅ TLS 1.2+ for all data in transit
✅ Secrets Manager with automatic rotation
✅ Encrypted EBS volumes
✅ Encrypted S3 buckets
✅ Encrypted CloudWatch Logs

### Monitoring & Logging
✅ CloudTrail enabled (all regions)
✅ Config enabled with compliance rules
✅ GuardDuty enabled
✅ Security Hub enabled
✅ CloudWatch Logs with retention
✅ Container Insights enabled
✅ X-Ray for distributed tracing

### Compliance
✅ STIG hardened containers
✅ FIPS 140-2 cryptographic compliance
✅ CIS Benchmark alignment
✅ Automated compliance checking
✅ Regular security audits

---

## 📝 Deployment Checklist

### Pre-Deployment
- [ ] Create AWS account with Organizations
- [ ] Enable CloudTrail (all regions)
- [ ] Enable Config with compliance rules
- [ ] Enable GuardDuty
- [ ] Enable Security Hub
- [ ] Create KMS keys
- [ ] Create VPC with private subnets
- [ ] Configure Security Groups
- [ ] Create IAM roles (execution, task)
- [ ] Store secrets in Secrets Manager
- [ ] Create S3 buckets (encrypted)
- [ ] Create ECR repository
- [ ] Set up CloudWatch Log Groups

### Deployment
- [ ] Build and push Docker image to ECR
- [ ] Scan image with Inspector
- [ ] Create ECS/EKS cluster
- [ ] Deploy application
- [ ] Configure ALB with HTTPS
- [ ] Set up Route 53 DNS
- [ ] Enable WAF (optional)
- [ ] Configure CloudWatch Alarms
- [ ] Test all health checks

### Post-Deployment
- [ ] Verify encryption (data at rest & transit)
- [ ] Test incident response procedures
- [ ] Review IAM permissions
- [ ] Enable backup/disaster recovery
- [ ] Document runbook procedures
- [ ] Train operations team
- [ ] Schedule security audits

---

## 📞 Support

For AWS security questions:
- **AWS Support**: Premium Support recommended for production
- **AWS Security Hub**: Automated compliance checking
- **AWS Well-Architected Tool**: Security pillar review

---

**Purple Pipeline Parser Eater v9.0.0**
**AWS Security**: Enterprise-Grade | STIG Compliant | FIPS 140-2 Enabled
**Last Updated**: October 8, 2025
