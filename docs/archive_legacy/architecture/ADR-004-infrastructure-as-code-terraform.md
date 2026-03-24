# ADR-004: Infrastructure as Code Using Terraform

## Status
ACCEPTED

## Date
2025-11-09

## Context

The Purple Pipeline Parser Eater deployment spans multiple cloud services requiring:
- Reproducible infrastructure creation
- Version-controlled configuration
- Consistent deployments across environments
- Team collaboration on infrastructure
- Clear audit trail of changes
- Easy rollback capability
- Multi-cloud flexibility

Managing infrastructure manually or through cloud console would be:
- Error-prone
- Hard to replicate across environments
- Difficult to track changes
- Impossible to audit
- Not scalable to multiple environments and regions

## Options Evaluated

### Option 1: Manual Cloud Console Management (Not Chosen)

**Characteristics:**
- Create resources by clicking through AWS console
- Document in external wiki/spreadsheet

**Cons:**
- Not reproducible
- Error-prone
- No version control
- No audit trail
- Hard to scale
- Team inconsistency
- Disaster recovery nightmare
- Not professional/enterprise

**Explicitly Rejected**: Industry best practice is "Never use console for infrastructure"

### Option 2: AWS CloudFormation (Considered)

**Characteristics:**
- AWS-native JSON/YAML templates
- Native AWS service integration

**Pros:**
- AWS-native, deeply integrated
- Free to use
- Works with AWS console, CLI, API

**Cons:**
- JSON verbose and error-prone
- Steep learning curve
- Limited error messages
- AWS-only (no GCP, Azure, etc.)
- Slower community adoption
- Less ecosystem tooling
- YAML syntax errors hard to debug
- No good option for multi-cloud

**Decision**: Not chosen because Terraform offers better experience

### Option 3: Terraform (Chosen)

**Characteristics:**
- Declarative Infrastructure as Code
- Cloud-agnostic (AWS, GCP, Azure, etc.)
- Open source with large ecosystem

**Pros:**
- Easy to read syntax (HCL)
- Cloud-agnostic (works across AWS, GCP, Azure)
- Large ecosystem of modules and providers
- Strong community support
- Better error messages than CloudFormation
- Excellent Terraform Cloud for team collaboration
- Can manage multiple cloud providers in same codebase
- Industry standard adoption
- Mature tooling and security scanning options
- Plan before apply (dry-run capability)
- State management with remote backends

**Cons:**
- Requires learning Terraform
- State file management complexity
- Initial setup more involved than console

### Option 4: Pulumi / CDK (Alternative)

**Characteristics:**
- Programming language-based IaC (Python, Go, TypeScript)

**Not chosen because:**
- Terraform is more established
- Team expertise with declarative approach
- Better for security teams (simpler to audit)
- Less code to maintain

## Decision

**Terraform is the Infrastructure as Code tool for Purple Pipeline Parser Eater deployment.**

### Rationale

1. **Reproducibility**: Exact same infrastructure every time
   - Same code → same resources
   - No manual steps or guesswork
   - Disaster recovery: Re-apply code to recover

2. **Version Control**: Infrastructure tracked in Git
   - Every change has commit message
   - Peer review before deployment
   - Rollback to previous versions
   - Blame/history tracking

3. **Documentation**: Code is self-documenting
   - Variables have descriptions
   - Comments explain complex logic
   - No separate documentation to maintain
   - Single source of truth

4. **Multi-cloud**: Terraform works everywhere
   - Same tool for AWS and GCP
   - Can migrate between clouds more easily
   - Skills transfer to other organizations

5. **Team Collaboration**
   - Everyone uses same infrastructure code
   - No tribal knowledge
   - Easier onboarding for new team members
   - Code review process before changes

6. **Automation**: Enables CI/CD for infrastructure
   - terraform plan in pull requests
   - Automated testing of changes
   - Automatic deployment on merge
   - Infrastructure follows software best practices

## Implementation Strategy

### File Organization

```
deployment/aws/terraform/
├── main.tf                    # Resource definitions
├── variables.tf              # Input variables with validation
├── outputs.tf                # Output values
├── terraform.tfvars.example  # Example values (commitable)
├── terraform.tfvars          # Actual values (GITIGNORED)
├── .pre-commit-config.yaml   # Validation hooks
├── .gitignore                # Prevent sensitive files
├── backends.tf               # State configuration (optional)
└── modules/
    ├── vpc/                  # Network module
    ├── eks-cluster/          # Kubernetes module
    ├── rds/                  # Database module
    ├── elasticache/          # Cache module
    ├── msk/                  # Kafka module
    ├── iam-roles/            # Identity management
    ├── kms/                  # Encryption keys
    ├── s3/                   # Storage
    ├── secrets/              # Secret management
    └── external-monitoring/           # CloudWatch integration
```

### Module Structure

Each module follows standard structure:

```
modules/vpc/
├── main.tf          # Resource definitions
├── variables.tf     # Input variables
├── outputs.tf       # Output values
└── README.md        # Module documentation
```

### State Management

**Local State (Development)**
```hcl
# For development, state stored locally
# Less secure, acceptable for non-production
terraform {
  backend "local" {
    path = "terraform.tfstate"
  }
}
```

**Remote State (Production)**
```hcl
# For production, state in S3 with encryption
terraform {
  backend "s3" {
    bucket         = "purple-pipeline-terraform-state"
    key            = "aws/production/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}
```

### Pre-commit Hooks

Automated validation before commit:

```yaml
hooks:
  - id: terraform_fmt          # Format check
  - id: terraform_validate     # Syntax check
  - id: terraform_tflint       # Best practices
  - id: terraform_tfsec        # Security scan
```

## Deployment Workflow

### Development (Local Machine)

```bash
# Initialize Terraform
terraform init

# Review planned changes
terraform plan -out=tfplan

# Review the plan
terraform show tfplan

# Apply if satisfied
terraform apply tfplan

# View outputs
terraform output
```

### Staging/Production (CI/CD)

```bash
# In GitHub Actions or similar
terraform init \
  -backend-config="bucket=purple-pipeline-state" \
  -backend-config="key=aws/prod/terraform.tfstate"

terraform plan -out=tfplan

# Plan reviewed in pull request

terraform apply tfplan  # On merge to main
```

## Security Practices

### Sensitive Data Protection

1. **Never commit secrets**
   ```hcl
   variable "database_password" {
     type      = string
     sensitive = true  # Prevents logging
   }
   ```

2. **Use Secrets Manager**
   ```hcl
   # Inject secrets from AWS Secrets Manager
   resource "aws_secretsmanager_secret" "db_password" {
     name = "purple-pipeline/db/password"
   }
   ```

3. **Gitignore Protection**
   ```
   # .gitignore
   terraform.tfvars          # Never commit actual values
   .terraform/               # Don't commit provider cache
   *.tfstate                 # Don't commit state files
   *.tfstate.*               # Don't commit state backups
   ```

### State File Security

1. **Encryption at Rest**
   - S3 with server-side encryption enabled
   - KMS key for encryption

2. **Access Control**
   - IAM policies restrict who can read state
   - Terraform Cloud for team access control

3. **Locking**
   - DynamoDB table prevents concurrent applies
   - Only one team member can apply at a time

## Validation and Testing

### Syntax Validation
```bash
terraform validate      # Check syntax
terraform fmt -check   # Check formatting
```

### Security Scanning
```bash
tfsec deployment/aws/terraform/        # Security issues
checkov -d deployment/aws/terraform/   # Compliance checks
```

### Integration Testing
```bash
terraform plan -out=tfplan
terraform apply tfplan -auto-approve   # In test environment
terraform destroy -auto-approve
```

## Advantages Over Alternatives

### vs Manual Console
| Aspect | Manual | Terraform |
|--------|--------|-----------|
| Reproducible | ✗ | ✓ |
| Version control | ✗ | ✓ |
| Audit trail | ✗ | ✓ |
| Code review | ✗ | ✓ |
| Rollback | Manual | Automatic |
| Multi-cloud | ✗ | ✓ |
| Automation | ✗ | ✓ |

### vs CloudFormation
| Aspect | CloudFormation | Terraform |
|--------|---|---|
| Multi-cloud | ✗ | ✓ |
| Syntax | JSON/YAML (verbose) | HCL (concise) |
| Error messages | Poor | Excellent |
| Community | Good | Excellent |
| Ecosystem | Moderate | Extensive |
| Team collaboration | Terraform Cloud | Better |

### vs Helm/Kustomize
These are complementary, not competing:
- **Terraform**: Infrastructure (VPC, RDS, EKS)
- **Helm/Kustomize**: Application deployment (pods, services)

## DevOps Integration

### GitHub Actions Pipeline

```yaml
name: Terraform Deployment

on:
  pull_request:
  push:
    branches: [main]

jobs:
  terraform:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: hashicorp/setup-terraform@v2

      - name: Terraform Format Check
        run: terraform fmt -check

      - name: Terraform Validation
        run: terraform validate

      - name: Plan
        run: terraform plan -out=tfplan

      - name: Apply (on main branch)
        if: github.ref == 'refs/heads/main'
        run: terraform apply tfplan
```

## Cost Tracking

### Cost Estimation
```bash
terraform plan -out=tfplan

# Use Terraform Cloud for cost estimation
# Shows estimated monthly costs before apply
```

### Resource Tagging
```hcl
locals {
  common_tags = {
    Project     = "purple-pipeline"
    Environment = var.environment
    ManagedBy   = "Terraform"
    CostCenter  = "engineering"
  }
}

resource "aws_instance" "example" {
  tags = local.common_tags
}
```

## Knowledge Base

### Essential Resources
1. **Terraform Documentation**: https://www.terraform.io/docs
2. **AWS Provider Docs**: https://registry.terraform.io/providers/hashicorp/aws/latest
3. **Best Practices**: https://www.terraform.io/docs/cloud/guides/recommended-practices
4. **Security**: https://www.terraform.io/docs/cloud/security

### Learning Path
1. Understand variables, resources, outputs
2. Learn state management concepts
3. Practice with modules
4. Setup Terraform Cloud for team collaboration
5. Implement CI/CD pipeline

## Future Evolution

### Terraform Cloud Integration
```
├── Version control (GitHub)
├── Terraform Cloud (state, runs, policy)
└── AWS (resources)
```

Benefits:
- Centralized state management
- Team collaboration
- Audit logs
- Policy as Code (Sentinel)

### Policy as Code (Sentinel)
```hcl
policy "require-tagging" {
  enforcement_level = "mandatory"

  rule {
    resource_types = ["aws_*"]

    condition = length(resource.tags) > 0
  }
}
```

## Related ADRs
- ADR-001: Choice of EKS Platform
- ADR-002: Multi-AZ Deployment
- ADR-003: Database Architecture

## Training and Onboarding

### For New Team Members
1. **Day 1**: Review this ADR and ADR-001 through ADR-003
2. **Day 2**: Review terraform.tfvars.example and outputs
3. **Day 3**: Practice terraform plan and apply in dev environment
4. **Day 4-5**: Make small change, submit PR, get review

### Terraform Best Practices Checklist
- [ ] All variables have descriptions
- [ ] All outputs have descriptions
- [ ] Sensitive outputs marked as sensitive
- [ ] Resources tagged appropriately
- [ ] No hardcoded values
- [ ] Remote state configured
- [ ] terraform fmt applied
- [ ] Pre-commit hooks installed
- [ ] State locked during apply
- [ ] Backup strategy documented

## Conclusion

Terraform provides the right balance of:
- Simplicity (easy to learn and use)
- Power (handles complex infrastructure)
- Flexibility (works across clouds)
- Maturity (proven in production)
- Community (large ecosystem)

It enables Infrastructure as Code best practices and positions the team for growth and scaling.

