# Root Directory Organization Guide
## Purple Pipeline Parser Eater

**Last Updated:** 2025-11-09
**Purpose:** Maintain clean, organized root directory structure

---

## Current Root Directory Structure

```
Purple-Pipeline-Parser-Eater/
├── README.md                           # Main project documentation
├── requirements.txt                    # Python dependencies (pinned with hashes)
├── requirements-minimal.txt            # Minimal dependencies
├── requirements.in                     # Source requirements for pip-compile
├── config.yaml.example                 # Example configuration (safe to commit)
├── docker-compose.yml                  # Docker Compose for local development
├── Dockerfile                          # Production Docker image
├── mypy.ini                            # Type checking configuration
├── .gitignore                          # Git ignore rules
├── .snyk                               # Snyk security policy
│
├── main.py                             # Main CLI entry point
├── orchestrator.py                     # Main orchestration logic
├── continuous_conversion_service.py    # Continuous service with web UI
├── gunicorn_config.py                  # Production WSGI server config
├── wsgi_production.py                  # WSGI application entry point
├── viewer.html                         # Standalone viewer utility
├── __init__.py                         # Package marker
│
├── components/                         # Core application components
├── services/                           # Service layer (ingestion, runtime, output)
├── utils/                              # Utility functions and helpers
├── orchestrator/                       # Orchestrator modules (phase-based)
├── scripts/                            # Standalone scripts and utilities
├── tests/                              # Test suite
├── deployment/                         # Infrastructure as Code (Terraform, K8s)
├── docs/                               # Comprehensive documentation
├── output/                             # Generated output files (git-ignored)
├── logs/                               # Application logs (git-ignored)
├── data/                               # Data files and caches (git-ignored)
└── deployment/kubernetes/              # Kubernetes manifests
```

---

## File Organization Rules

### ✅ What Belongs in Root

**Essential Project Files:**
- `README.md` - Main project documentation
- `LICENSE` - Project license
- `.gitignore` - Git ignore rules
- `.snyk` - Security policy

**Dependency Management:**
- `requirements.txt` - Pinned dependencies with hashes
- `requirements-minimal.txt` - Minimal dependencies
- `requirements.in` - Source requirements

**Configuration:**
- `config.yaml.example` - Example configuration (SAFE)
- `mypy.ini` - Type checking config
- `docker-compose.yml` - Local development setup
- `Dockerfile` - Production container image

**Main Entry Points:**
- `main.py` - CLI interface
- `orchestrator.py` - Core orchestration (or wrapper to orchestrator/)
- `continuous_conversion_service.py` - Continuous service
- `gunicorn_config.py` - Production server config
- `wsgi_production.py` - WSGI entry point

**Package Markers:**
- `__init__.py` - Makes root a Python package

**Utilities:**
- `viewer.html` - Standalone HTML viewer

### ❌ What Does NOT Belong in Root

**Status Reports & Analysis:**
- Move to `docs/remediation/` or `docs/status/`
- Examples: `*_SUMMARY.md`, `*_REPORT.md`, `*_ANALYSIS.md`

**Development Guides:**
- Move to `docs/development/`
- Examples: `*_CHECKLIST.md`, `*_TASKS.md`, `*_PLAN.md`

**Agent Task Prompts:**
- Move to `docs/development/agent-tasks/`
- Examples: `AGENT_*.md`, `.agent-tasks/*`

**Secrets & Credentials:**
- NEVER commit: `config.yaml`, `.env`, `*.key`, `*.pem`
- Use `.gitignore` to prevent accidental commits

**Generated Output:**
- Move to `output/`, `logs/`, `data/` directories
- Examples: `*.log`, `*.json` (output files), `*.db` (temp databases)

**Large Binary Files:**
- Do not vendor large binaries in this repository
- Use external artifact storage and document retrieval steps

---

## Recently Cleaned (2025-11-09)

### Files Moved to docs/remediation/

- `COMPLETE_REMEDIATION_REPORT.md` → `docs/remediation/`
- `REMEDIATION_PLAN.md` → `docs/remediation/`
- `REMEDIATION_SUMMARY.md` → `docs/remediation/`
- `REFACTORING_PLAN_PHASE2.md` → `docs/remediation/`
- `WORK_SESSION_SUMMARY.md` → `docs/remediation/`

### Files Moved to docs/development/

- `APPLICATION_TEST_RESULTS.md` → `docs/development/`
- `GITHUB_READY_CHECKLIST.md` → `docs/development/`

### Files Moved to docs/development/agent-tasks/

- `.agent-tasks/README.md` → `docs/development/agent-tasks/`
- `.agent-tasks/AGENT_1_REFACTOR_WEB_FEEDBACK_UI.md` → `docs/development/agent-tasks/`
- `.agent-tasks/AGENT_2_REFACTOR_ORCHESTRATOR.md` → `docs/development/agent-tasks/`
- `.agent-tasks/AGENT_3_REFACTOR_OBSERVO_API_CLIENT.md` → `docs/development/agent-tasks/`

### Files Moved to docs/

- `SETUP.md` → `docs/SETUP_GUIDE.md`

### Files Removed from Git Tracking

- `config.yaml` - Removed from git (was accidentally committed)
  - **SECURITY:** This file may contain API keys and secrets
  - Already in `.gitignore`
  - Use `config.yaml.example` as template

---

## Current Root Directory Contents

**After cleanup, the root should only contain:**

```
Root/
├── README.md                    # Main documentation
├── LICENSE                      # Project license
├── .gitignore                   # Git rules
├── .snyk                        # Security policy
│
├── requirements.txt             # Dependencies
├── requirements-minimal.txt     # Minimal deps
├── requirements.in              # Source deps
│
├── config.yaml.example          # Config template
├── docker-compose.yml           # Docker Compose
├── Dockerfile                   # Container image
├── mypy.ini                     # Type checking
│
├── main.py                      # CLI entry point
├── orchestrator.py              # Orchestration
├── continuous_conversion_service.py  # Continuous service
├── gunicorn_config.py           # Production server
├── wsgi_production.py           # WSGI app
├── viewer.html                  # HTML viewer
├── __init__.py                  # Package marker
│
└── [directories]/               # All other content in subdirectories
```

**Total files in root:** ~17 files (down from 24+)

---

## Directory Organization

### docs/

**Purpose:** All documentation

**Subdirectories:**
- `docs/architecture/` - System architecture docs
- `docs/deployment/` - Deployment guides
- `docs/development/` - Development guides and checklists
- `docs/development/agent-tasks/` - Automated refactoring prompts
- `docs/remediation/` - Code quality improvement reports
- `docs/security/` - Security documentation and policies
- `docs/status/` - Project status and summaries
- `docs/historical/` - Historical documentation (archive)
- `docs/rag/` - RAG system documentation
- `docs/verification/` - Verification and testing docs

### components/

**Purpose:** Core application components

### services/

**Purpose:** Service layer (Agent 1, 2, 3)

### utils/

**Purpose:** Utility functions and helpers

### scripts/

**Purpose:** Standalone scripts and tools

### tests/

**Purpose:** Test suite

### deployment/

**Purpose:** Infrastructure as Code
- `deployment/aws/terraform/` - AWS infrastructure
- `deployment/gcp/terraform/` - GCP infrastructure
- `deployment/kubernetes/` - K8s manifests

### output/

**Purpose:** Generated output files (git-ignored)

### logs/

**Purpose:** Application logs (git-ignored)

### data/

**Purpose:** Data files and caches (git-ignored)

---

## Maintenance Guidelines

### When Adding New Files

**Documentation:**
- Analysis reports → `docs/remediation/` or `docs/status/`
- Setup guides → `docs/` (root) or `docs/deployment/`
- Architecture docs → `docs/architecture/`
- Security docs → `docs/security/`
- Development guides → `docs/development/`

**Code:**
- Components → `components/`
- Services → `services/`
- Utilities → `utils/`
- Tests → `tests/`
- Scripts → `scripts/`

**Configuration:**
- Example configs → Keep in root with `.example` suffix
- Actual configs → NEVER commit, ensure in `.gitignore`

**Infrastructure:**
- Terraform → `deployment/<cloud>/terraform/`
- Kubernetes → `deployment/kubernetes/`
- Docker → Root directory (Dockerfile, docker-compose.yml)

### Regular Cleanup Tasks

**Weekly:**
- Check for new `.md` files in root
- Move to appropriate `docs/` subdirectory
- Update references if needed

**Monthly:**
- Review `docs/` organization
- Archive outdated docs to `docs/historical/`
- Update this guide if structure changes

**Before Releases:**
- Verify no secrets in git
- Check `.gitignore` is comprehensive
- Ensure root is clean and organized
- Run: `git status` to verify

---

## Security Checklist

### Files That Should NEVER Be Committed

- ❌ `config.yaml` - May contain API keys
- ❌ `.env` - Environment variables with secrets
- ❌ `*.key`, `*.pem` - Private keys and certificates
- ❌ `credentials.json` - Any credentials files
- ❌ `secrets.yaml` - Secrets configuration
- ❌ Any file with actual API keys or tokens

### Verification Commands

**Check for accidentally committed secrets:**
```bash
# Check git status
git status

# Search for potential secrets
grep -r "sk-ant-" . --include="*.yaml" --include="*.yml"
grep -r "ghp_" . --include="*.yaml" --include="*.yml"

# Check if config.yaml is tracked
git ls-files | grep config.yaml
# Should return nothing (config.yaml should not be tracked)
```

**If config.yaml is tracked:**
```bash
# Remove from git but keep local file
git rm --cached config.yaml

# Verify it's in .gitignore
grep "config.yaml" .gitignore

# Commit the removal
git add .gitignore
git commit -m "Remove config.yaml from git tracking (security)"
```

---

## Clean Root Checklist

- [x] Only essential files in root
- [x] All reports moved to docs/
- [x] All development docs in docs/development/
- [x] Agent tasks in docs/development/agent-tasks/
- [x] config.yaml removed from git tracking
- [x] .gitignore properly configured
- [x] No secrets in committed files
- [x] References updated in documentation
- [x] README.md updated with new paths

---

## Quick Reference

### Finding Moved Files

**Remediation Reports:**
- Location: `docs/remediation/`
- Files:
  - `COMPLETE_REMEDIATION_REPORT.md`
  - `REMEDIATION_PLAN.md`
  - `REMEDIATION_SUMMARY.md`
  - `REFACTORING_PLAN_PHASE2.md`
  - `WORK_SESSION_SUMMARY.md`

**Agent Tasks:**
- Location: `docs/development/agent-tasks/`
- Files:
  - `README.md` (execution guide)
  - `AGENT_1_REFACTOR_WEB_FEEDBACK_UI.md`
  - `AGENT_2_REFACTOR_ORCHESTRATOR.md`
  - `AGENT_3_REFACTOR_OBSERVO_API_CLIENT.md`

**Development Docs:**
- Location: `docs/development/`
- Files:
  - `APPLICATION_TEST_RESULTS.md`
  - `GITHUB_READY_CHECKLIST.md`

**Setup Guides:**
- Location: `docs/`
- Files:
  - `SETUP_GUIDE.md` (main setup)
  - `SETUP_ENVIRONMENT_VARIABLES.md` (env vars)
  - `QUICK_START_FINAL_SETUP.md` (quick start)

---

## Benefits of Clean Root

✅ **Easier Navigation**
- Essential files immediately visible
- Less clutter
- Clear purpose for each file

✅ **Better Security**
- Reduced risk of committing secrets
- Clear separation of example vs actual configs
- Easier to audit

✅ **Improved Maintainability**
- Logical organization
- Easy to find files
- Consistent structure

✅ **Professional Appearance**
- Clean project structure
- Well-organized documentation
- Enterprise-grade organization

---

## Automated Cleanup Script

For future cleanup, you can use this script:

```bash
#!/bin/bash
# cleanup_root.sh - Organize root directory files

# Move status reports to docs/status/
mv *_STATUS.md *_SUMMARY.md docs/status/ 2>/dev/null

# Move analysis reports to docs/remediation/
mv *_REPORT.md *_ANALYSIS.md docs/remediation/ 2>/dev/null

# Move development docs to docs/development/
mv *_CHECKLIST.md *_PLAN.md *_TASKS.md docs/development/ 2>/dev/null

# Check for secrets in tracked files
echo "Checking for accidentally committed secrets..."
git ls-files | grep -E "config\.yaml$|\.env$|.*\.key$|.*\.pem$|credentials\.json$"

# If any found, alert user
if [ $? -eq 0 ]; then
    echo "⚠️  WARNING: Potential secrets found in git tracking!"
    echo "Review and remove with: git rm --cached <filename>"
fi

echo "✓ Root cleanup complete"
```

---

## Contact & Support

**Questions about organization?**
- Check: [docs/INDEX.md](docs/INDEX.md) for complete documentation index
- Review: This guide for root directory rules
- Consult: Project maintainers for structural changes

---

**Document Version:** 1.0
**Created:** 2025-11-09
**Last Cleanup:** 2025-11-09
**Next Review:** 2025-12-09 (monthly)

---

**END OF GUIDE**
