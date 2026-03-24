# 📁 Repository Reorganization Plan

**Date**: 2025-11-07
**Purpose**: Clean up root directory and organize files logically

---

## Current Problem

The root directory contains **100+ markdown files** and **20+ Python scripts** that make navigation difficult.

## Organization Strategy

### Files to KEEP in Root
- README.md (main documentation)
- SETUP.md (setup guide)
- requirements.txt, requirements-minimal.txt
- main.py (main orchestrator entry point)
- orchestrator.py (core orchestrator)
- continuous_conversion_service.py (continuous service)
- config.yaml (main configuration)
- docker-compose.yml, Dockerfile
- .gitignore, LICENSE

### New Folder Structure

```
Purple-Pipline-Parser-Eater/
├── README.md                                    ← Keep
├── SETUP.md                                     ← Keep
├── requirements.txt                             ← Keep
├── main.py                                      ← Keep
├── orchestrator.py                              ← Keep
├── continuous_conversion_service.py             ← Keep
│
├── docs/
│   ├── agent-prompts/                          ← NEW: Agent implementation prompts
│   │   ├── AGENT_1_EVENT_INGESTION_PROMPT.md
│   │   ├── AGENT_2_TRANSFORM_PIPELINE_PROMPT.md
│   │   └── AGENT_3_OBSERVO_OUTPUT_PROMPT.md
│   │
│   ├── architecture/                           ← NEW: Architecture docs
│   │   ├── Hybrid_Architecture_Plan.md
│   │   ├── DATAPLANE_INTEGRATION_STATUS.md
│   │   ├── DATAPLANE_CURRENT_FLOW.md
│   │   └── AGENT_2_RUNTIME_SERVICE_ARCHITECTURE.md
│   │
│   ├── security/                               ← Security documentation
│   │   ├── SECURITY_AUDIT_UPDATE_2025-10-15.md
│   │   ├── SECURITY_FIXES_SUMMARY.md
│   │   ├── AWS_SECURITY_HARDENING_GUIDE.md
│   │   └── (other security docs)
│   │
│   ├── rag/                                    ← RAG documentation
│   │   ├── RAG_SETUP_GUIDE.md
│   │   ├── RAG_QUICK_REFERENCE.md
│   │   ├── RAG_DATA_AND_ML_STRATEGY.md
│   │   └── (other RAG docs)
│   │
│   ├── deployment/                             ← Deployment guides
│   │   ├── PRODUCTION_DEPLOYMENT_GUIDE.md
│   │   ├── DOCKER_DEPLOYMENT_GUIDE.md
│   │   └── PHASE_1_ACTION_PLAN.md
│   │
│   ├── verification/                           ← NEW: Verification reports
│   │   ├── AGENT_IMPLEMENTATION_VERIFICATION.md
│   │   ├── VERIFICATION_SUMMARY.md
│   │   └── EVENT_PIPELINE_QUICK_START.md
│   │
│   └── historical/                             ← OLD: Archived status files
│       ├── IMPLEMENTATION_COMPLETE*.md
│       ├── WORK_COMPLETE*.md
│       ├── PHASE_*_COMPLETE.md
│       └── (other historical docs)
│
├── scripts/
│   ├── start_event_ingestion.py               ← Keep
│   ├── start_runtime_service.py               ← Keep
│   ├── start_output_service.py                ← Keep
│   │
│   ├── rag/                                    ← RAG scripts
│   │   ├── auto_populate_rag.py
│   │   ├── populate_from_local.py
│   │   ├── populate_rag_knowledge.py
│   │   ├── ingest_observo_docs.py
│   │   ├── ingest_s1_docs.py
│   │   ├── ingest_all_sources.py
│   │   ├── start_rag_autosync.py
│   │   ├── start_rag_autosync_github.py
│   │   ├── start_rag_autosync_dataplane.py
│   │   └── rag_auto_updater.py
│   │
│   ├── demos/                                  ← Demo scripts
│   │   ├── demo_10_parsers.py
│   │   └── run_demo.py
│   │
│   └── utils/                                  ← Utility scripts
│       ├── fix_imports.py
│       ├── fix_docker_build.py
│       ├── fix_type_hints.py
│       ├── test_xss_protection.py
│       ├── test_lupa_validation.py
│       ├── test_failed_parsers.py
│       └── preflight_check.py
```

---

## Files to Move

### Agent Prompts → docs/agent-prompts/
- AGENT_1_EVENT_INGESTION_PROMPT.md
- AGENT_2_TRANSFORM_PIPELINE_PROMPT.md
- AGENT_3_OBSERVO_OUTPUT_PROMPT.md

### Architecture Docs → docs/architecture/
- Hybrid_Architecture_Plan.md
- DATAPLANE_INTEGRATION_STATUS.md
- DATAPLANE_CURRENT_FLOW.md
- PHASE_1_ACTION_PLAN.md
- INVESTIGATION_SUMMARY.md

### Verification Docs → docs/verification/
- AGENT_IMPLEMENTATION_VERIFICATION.md
- VERIFICATION_SUMMARY.md
- EVENT_PIPELINE_QUICK_START.md

### Security Docs → docs/security/
- SECURITY_AUDIT_UPDATE_2025-10-15.md
- SECURITY_FIXES_SUMMARY.md
- SECURITY_AUDIT_REPORT.md
- AWS_SECURITY_HARDENING_GUIDE.md
- AWS_SECURITY_SUMMARY.md
- SECURITY_VALIDATION_CHECKLIST.md
- COMPREHENSIVE_SECURITY_AUDIT.md
- POST_FIX_SECURITY_ASSESSMENT.md
- VULNERABILITY_REMEDIATION_PLAN.md
- PRODUCTION_SECURITY_HARDENING_PLAN.md
- SECURITY_ITEMS_WE_DO_NOT_HAVE.md
- CSRF_IMPACT_ANALYSIS.md

### RAG Docs → docs/rag/
- RAG_SETUP_GUIDE.md
- RAG_SETUP_COMPLETE.md
- RAG_QUICK_REFERENCE.md
- RAG_DATA_AND_ML_STRATEGY.md
- RAG_IMPLEMENTATION_COMPLETE.md
- RAG_IMPLEMENTATION_PLAN.md
- RAG_POPULATION_STATUS.md
- RAG_PREFLIGHT_STATUS.md
- RAG_QUICK_START.md
- RAG_COMPLETE_IMPLEMENTATION.md
- RAG_EXTERNAL_SOURCES_GUIDE.md
- RAG_AUTO_SYNC_GUIDE.md
- POPULATE_RAG_NOW.md

### Deployment Docs → docs/deployment/
- PRODUCTION_DEPLOYMENT_GUIDE.md
- DOCKER_DEPLOYMENT_GUIDE.md
- DOCKER_README.md
- DOCKER_TESTING_PLAN.md
- DOCKER_END_TO_END_TEST_PLAN.md
- DEPLOYMENT_COMPLETE.md
- PRODUCTION_CONVERSION_PLAN.md
- PRODUCTION_CONVERSION_SUMMARY.md

### Historical/Archive → docs/historical/
- IMPLEMENTATION_COMPLETE.md
- IMPLEMENTATION_COMPLETE_SUMMARY.md
- IMPLEMENTATION_STATUS.md
- WORK_COMPLETE_SUMMARY.md
- WORK_COMPLETE_FINAL.md
- FINAL_IMPLEMENTATION_SUMMARY.md
- FIXES_APPLIED.md
- FIXES_APPLIED_COMPLETE.md
- FINAL_TEST_RESULTS_AND_DOCUMENTATION.md
- PHASE_1_COMPLETE.md
- PHASE_2_COMPLETE.md
- PHASE_3_DETAILED_PLAN.md
- PHASE_4_HARDENING_COMPLETE.md
- PHASE_5_COMPLETE.md
- PHASE_5_TESTING_PLAN.md
- PHASE_2_START_DOCKER.md
- PHASE_2_SECURITY_HARDENING_COMPLETE.md
- PHASE_3_COMPLIANCE_HARDENING_COMPLETE.md
- PHASES_2-5_IMPLEMENTATION_GUIDE.md
- CONTINUOUS_SERVICE_COMPLETE.md
- GITHUB_CLOUD_SYNC_COMPLETE.md
- GITHUB_READY_SUMMARY.md
- GITHUB_UPLOAD_CHECKLIST.md
- UPLOAD_TO_GITHUB_NOW.md
- QUICK_START_GITHUB_SYNC.md
- OBSERVO_INTEGRATION_STATUS.md
- OBSERVO_WORK_COMPLETE.md
- OBSERVO_INTEGRATION_COMPLETE.md
- ORCHESTRATOR_INTEGRATION_COMPLETE.md
- DIRECTOR_REQUIREMENTS_IMPLEMENTATION.md
- DIRECTOR_REQUIREMENTS_SATISFIED.md
- QUICK_REFERENCE_DIRECTOR.md
- MISSING_PIECES_ANALYSIS.md
- CRITICAL_FIXES_REQUIRED.md
- FAILED_PARSERS_ANALYSIS.md
- FAILED_PARSERS_DETAILED_REPORT_2025-10-13.md
- COMPREHENSIVE_FAILURE_ANALYSIS_AND_REMEDIATION_PLAN.md
- REMEDIATION_TEST_RESULTS_2025-10-13.md
- SDL_AUDIT_IMPLEMENTATION.md
- SDL_AUDIT_FINAL_STATUS.md
- SECURITY_WORK_SUMMARY.md
- WEB_UI_FIX_PLAN.md
- FOLDER_RENAMED.md
- PROJECT_STATUS_FINAL.md
- PRODUCTION_READINESS_REPORT.md
- TEAM_EMAIL_SUMMARY.md
- ONECON_TEAM_EMAIL.md
- COMPLETE_APPLICATION_OVERVIEW_EMAIL.md
- README_UPDATE_REQUIRED.md
- REPOSITORY_STRUCTURE.md
- FUTURE_ENHANCEMENTS.md
- RELEASE_ROADMAP.md

### Special Guides → docs/ (root)
- START_HERE.md → docs/START_HERE.md
- WEB_UI_VERIFICATION.md → docs/WEB_UI_VERIFICATION.md
- WHAT_YOU_ACTUALLY_NEED.md → docs/WHAT_YOU_ACTUALLY_NEED.md
- YOUR_STATUS.md → docs/YOUR_STATUS.md
- PROJECT_SUMMARY.md → docs/PROJECT_SUMMARY.md
- S1_INTEGRATION_GUIDE.md → docs/S1_INTEGRATION_GUIDE.md
- DEMO_STATUS.md → docs/demos/
- 10_PARSER_DEMO_GUIDE.md → docs/demos/
- DEMO_QUICK_REF.md → docs/demos/

### RAG Scripts → scripts/rag/
- auto_populate_rag.py
- populate_from_local.py
- populate_from_local_auto.py
- populate_rag_knowledge.py
- ingest_observo_docs.py
- ingest_s1_docs.py
- ingest_all_sources.py
- start_rag_autosync.py
- start_rag_autosync_github.py
- start_rag_autosync_dataplane.py
- rag_auto_updater.py

### Demo Scripts → scripts/demos/
- demo_10_parsers.py
- run_demo.py

### Utility Scripts → scripts/utils/
- fix_imports.py
- fix_docker_build.py
- fix_type_hints.py
- test_xss_protection.py
- test_lupa_validation.py
- test_failed_parsers.py
- preflight_check.py

### Text Files → Archive or Convert
- QUICK_START_REFERENCE.txt → Convert to MD or archive
- AGENT_2_COMPLETION_SUMMARY.txt → docs/historical/

---

## Implementation

Run the reorganization script:
```bash
python scripts/reorganize_repository.py
```

This will:
1. Create all necessary folders
2. Move files to appropriate locations
3. Update any broken links in README
4. Create a backup of moved files
5. Generate a summary report
