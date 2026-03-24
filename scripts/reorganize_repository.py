#!/usr/bin/env python3
"""
Repository Reorganization Script

Cleans up the root directory by moving files to appropriate folders.
Creates backups and generates a summary report.

Usage:
    python scripts/reorganize_repository.py [--dry-run] [--backup]
"""

import os
import shutil
from pathlib import Path
from typing import List, Tuple
import argparse
from datetime import datetime

# Get repository root
REPO_ROOT = Path(__file__).parent.parent

# Reorganization mappings
FILE_MOVES = {
    # Agent Prompts
    "docs/agent-prompts": [
        "AGENT_1_EVENT_INGESTION_PROMPT.md",
        "AGENT_2_TRANSFORM_PIPELINE_PROMPT.md",
        "AGENT_3_OBSERVO_OUTPUT_PROMPT.md",
    ],

    # Architecture Documentation
    "docs/architecture": [
        "DATAPLANE_INTEGRATION_STATUS.md",
        "DATAPLANE_CURRENT_FLOW.md",
        "PHASE_1_ACTION_PLAN.md",
        "INVESTIGATION_SUMMARY.md",
    ],

    # Verification Documentation
    "docs/verification": [
        "AGENT_IMPLEMENTATION_VERIFICATION.md",
        "VERIFICATION_SUMMARY.md",
        "EVENT_PIPELINE_QUICK_START.md",
    ],

    # Security Documentation
    "docs/security": [
        "SECURITY_AUDIT_UPDATE_2025-10-15.md",
        "SECURITY_FIXES_SUMMARY.md",
        "SECURITY_AUDIT_REPORT.md",
        "AWS_SECURITY_HARDENING_GUIDE.md",
        "AWS_SECURITY_SUMMARY.md",
        "SECURITY_VALIDATION_CHECKLIST.md",
        "COMPREHENSIVE_SECURITY_AUDIT.md",
        "POST_FIX_SECURITY_ASSESSMENT.md",
        "VULNERABILITY_REMEDIATION_PLAN.md",
        "PRODUCTION_SECURITY_HARDENING_PLAN.md",
        "SECURITY_ITEMS_WE_DO_NOT_HAVE.md",
        "CSRF_IMPACT_ANALYSIS.md",
    ],

    # RAG Documentation
    "docs/rag": [
        "RAG_SETUP_GUIDE.md",
        "RAG_SETUP_COMPLETE.md",
        "RAG_QUICK_REFERENCE.md",
        "RAG_DATA_AND_ML_STRATEGY.md",
        "RAG_IMPLEMENTATION_COMPLETE.md",
        "RAG_IMPLEMENTATION_PLAN.md",
        "RAG_POPULATION_STATUS.md",
        "RAG_PREFLIGHT_STATUS.md",
        "RAG_QUICK_START.md",
        "RAG_COMPLETE_IMPLEMENTATION.md",
        "RAG_EXTERNAL_SOURCES_GUIDE.md",
        "RAG_AUTO_SYNC_GUIDE.md",
        "POPULATE_RAG_NOW.md",
    ],

    # Deployment Documentation
    "docs/deployment": [
        "PRODUCTION_DEPLOYMENT_GUIDE.md",
        "DOCKER_DEPLOYMENT_GUIDE.md",
        "DOCKER_README.md",
        "DOCKER_TESTING_PLAN.md",
        "DOCKER_END_TO_END_TEST_PLAN.md",
        "DEPLOYMENT_COMPLETE.md",
        "PRODUCTION_CONVERSION_PLAN.md",
        "PRODUCTION_CONVERSION_SUMMARY.md",
    ],

    # Demo Documentation
    "docs/demos": [
        "DEMO_STATUS.md",
        "10_PARSER_DEMO_GUIDE.md",
        "DEMO_QUICK_REF.md",
    ],

    # General Docs (move to docs root)
    "docs": [
        "START_HERE.md",
        "WEB_UI_VERIFICATION.md",
        "WHAT_YOU_ACTUALLY_NEED.md",
        "YOUR_STATUS.md",
        "PROJECT_SUMMARY.md",
        "S1_INTEGRATION_GUIDE.md",
    ],

    # Historical/Archive
    "docs/historical": [
        "IMPLEMENTATION_COMPLETE.md",
        "IMPLEMENTATION_COMPLETE_SUMMARY.md",
        "IMPLEMENTATION_STATUS.md",
        "WORK_COMPLETE_SUMMARY.md",
        "WORK_COMPLETE_FINAL.md",
        "FINAL_IMPLEMENTATION_SUMMARY.md",
        "FIXES_APPLIED.md",
        "FIXES_APPLIED_COMPLETE.md",
        "FINAL_TEST_RESULTS_AND_DOCUMENTATION.md",
        "PHASE_1_COMPLETE.md",
        "PHASE_2_COMPLETE.md",
        "PHASE_3_DETAILED_PLAN.md",
        "PHASE_4_HARDENING_COMPLETE.md",
        "PHASE_5_COMPLETE.md",
        "PHASE_5_TESTING_PLAN.md",
        "PHASE_2_START_DOCKER.md",
        "PHASE_2_SECURITY_HARDENING_COMPLETE.md",
        "PHASE_3_COMPLIANCE_HARDENING_COMPLETE.md",
        "PHASES_2-5_IMPLEMENTATION_GUIDE.md",
        "CONTINUOUS_SERVICE_COMPLETE.md",
        "GITHUB_CLOUD_SYNC_COMPLETE.md",
        "GITHUB_READY_SUMMARY.md",
        "GITHUB_UPLOAD_CHECKLIST.md",
        "UPLOAD_TO_GITHUB_NOW.md",
        "QUICK_START_GITHUB_SYNC.md",
        "OBSERVO_INTEGRATION_STATUS.md",
        "OBSERVO_WORK_COMPLETE.md",
        "OBSERVO_INTEGRATION_COMPLETE.md",
        "ORCHESTRATOR_INTEGRATION_COMPLETE.md",
        "DIRECTOR_REQUIREMENTS_IMPLEMENTATION.md",
        "DIRECTOR_REQUIREMENTS_SATISFIED.md",
        "QUICK_REFERENCE_DIRECTOR.md",
        "MISSING_PIECES_ANALYSIS.md",
        "CRITICAL_FIXES_REQUIRED.md",
        "FAILED_PARSERS_ANALYSIS.md",
        "FAILED_PARSERS_DETAILED_REPORT_2025-10-13.md",
        "COMPREHENSIVE_FAILURE_ANALYSIS_AND_REMEDIATION_PLAN.md",
        "REMEDIATION_TEST_RESULTS_2025-10-13.md",
        "SDL_AUDIT_IMPLEMENTATION.md",
        "SDL_AUDIT_FINAL_STATUS.md",
        "SECURITY_WORK_SUMMARY.md",
        "WEB_UI_FIX_PLAN.md",
        "FOLDER_RENAMED.md",
        "PROJECT_STATUS_FINAL.md",
        "PRODUCTION_READINESS_REPORT.md",
        "TEAM_EMAIL_SUMMARY.md",
        "ONECON_TEAM_EMAIL.md",
        "COMPLETE_APPLICATION_OVERVIEW_EMAIL.md",
        "README_UPDATE_REQUIRED.md",
        "REPOSITORY_STRUCTURE.md",
        "FUTURE_ENHANCEMENTS.md",
        "RELEASE_ROADMAP.md",
        "QUICK_START_REFERENCE.txt",
        "AGENT_2_COMPLETION_SUMMARY.txt",
    ],

    # RAG Scripts
    "scripts/rag": [
        "auto_populate_rag.py",
        "populate_from_local.py",
        "populate_from_local_auto.py",
        "populate_rag_knowledge.py",
        "ingest_observo_docs.py",
        "ingest_s1_docs.py",
        "ingest_all_sources.py",
        "start_rag_autosync.py",
        "start_rag_autosync_github.py",
        "start_rag_autosync_dataplane.py",
        "rag_auto_updater.py",
    ],

    # Demo Scripts
    "scripts/demos": [
        "demo_10_parsers.py",
        "run_demo.py",
    ],

    # Utility Scripts
    "scripts/utils": [
        "fix_imports.py",
        "fix_docker_build.py",
        "fix_type_hints.py",
        "test_xss_protection.py",
        "test_lupa_validation.py",
        "test_failed_parsers.py",
        "preflight_check.py",
    ],
}


def create_backup(dry_run: bool = False) -> Path:
    """Create backup of root directory before reorganization."""
    backup_dir = REPO_ROOT / "backup_before_reorganization"

    if dry_run:
        print(f"[DRY RUN] Would create backup at: {backup_dir}")
        return backup_dir

    if backup_dir.exists():
        # Add timestamp if backup already exists
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = REPO_ROOT / f"backup_before_reorganization_{timestamp}"

    backup_dir.mkdir(parents=True, exist_ok=True)
    print(f"✓ Created backup directory: {backup_dir}")
    return backup_dir


def create_folders(dry_run: bool = False):
    """Create all necessary destination folders."""
    folders = set(FILE_MOVES.keys())

    for folder in sorted(folders):
        folder_path = REPO_ROOT / folder

        if dry_run:
            if not folder_path.exists():
                print(f"[DRY RUN] Would create: {folder}")
        else:
            folder_path.mkdir(parents=True, exist_ok=True)
            print(f"✓ Created: {folder}")


def move_files(dry_run: bool = False, backup_dir: Path = None) -> Tuple[List[str], List[str], List[str]]:
    """Move files to their destination folders."""
    moved = []
    skipped = []
    errors = []

    for dest_folder, files in FILE_MOVES.items():
        for filename in files:
            source = REPO_ROOT / filename
            destination = REPO_ROOT / dest_folder / filename

            if not source.exists():
                skipped.append(f"{filename} (not found)")
                continue

            if dry_run:
                print(f"[DRY RUN] Would move: {filename} → {dest_folder}/")
                moved.append(filename)
            else:
                try:
                    # Backup original file
                    if backup_dir:
                        backup_file = backup_dir / filename
                        shutil.copy2(source, backup_file)

                    # Move file
                    shutil.move(str(source), str(destination))
                    moved.append(filename)
                    print(f"✓ Moved: {filename} → {dest_folder}/")

                except Exception as e:
                    errors.append(f"{filename}: {str(e)}")
                    print(f"✗ Error moving {filename}: {e}")

    return moved, skipped, errors


def generate_report(moved: List[str], skipped: List[str], errors: List[str], dry_run: bool = False):
    """Generate reorganization summary report."""
    report_path = REPO_ROOT / "REORGANIZATION_REPORT.md"

    content = f"""# Repository Reorganization Report

**Date**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Mode**: {"DRY RUN" if dry_run else "ACTUAL"}

## Summary

- **Files Moved**: {len(moved)}
- **Files Skipped**: {len(skipped)} (not found)
- **Errors**: {len(errors)}

## Files Moved ({len(moved)})

"""

    for dest_folder, files in FILE_MOVES.items():
        files_in_folder = [f for f in files if f in moved]
        if files_in_folder:
            content += f"\n### {dest_folder}/ ({len(files_in_folder)} files)\n\n"
            for f in files_in_folder:
                content += f"- {f}\n"

    if skipped:
        content += f"\n## Files Skipped ({len(skipped)})\n\n"
        for f in skipped:
            content += f"- {f}\n"

    if errors:
        content += f"\n## Errors ({len(errors)})\n\n"
        for e in errors:
            content += f"- {e}\n"

    content += """
---

## New Directory Structure

```
Purple-Pipline-Parser-Eater/
├── README.md
├── SETUP.md
├── main.py
├── orchestrator.py
├── continuous_conversion_service.py
├── requirements.txt
│
├── docs/
│   ├── agent-prompts/          ← Agent implementation prompts
│   ├── architecture/            ← Architecture documentation
│   ├── verification/            ← Verification reports
│   ├── security/                ← Security documentation
│   ├── rag/                     ← RAG documentation
│   ├── deployment/              ← Deployment guides
│   ├── demos/                   ← Demo documentation
│   └── historical/              ← Archived status files
│
├── scripts/
│   ├── start_event_ingestion.py
│   ├── start_runtime_service.py
│   ├── start_output_service.py
│   ├── rag/                     ← RAG population scripts
│   ├── demos/                   ← Demo scripts
│   └── utils/                   ← Utility scripts
│
├── components/                   ← Application components
├── services/                     ← Application services
├── config/                       ← Configuration files
└── tests/                        ← Test suite
```

## What's in the Root Now

Only essential files remain:
- README.md (main documentation)
- SETUP.md (setup guide)
- main.py (orchestrator entry)
- orchestrator.py (core logic)
- continuous_conversion_service.py (continuous service)
- requirements.txt (dependencies)
- config.yaml (main config)
- docker-compose.yml, Dockerfile
- .gitignore, LICENSE

All documentation is now organized in `docs/` subdirectories.
All scripts are now organized in `scripts/` subdirectories.
"""

    if dry_run:
        print(f"\n[DRY RUN] Would generate report at: {report_path}")
        print("\n" + "="*80)
        print(content)
        print("="*80)
    else:
        report_path.write_text(content, encoding="utf-8")
        print(f"\n✓ Generated report: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Reorganize Purple Pipeline Parser Eater repository")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be moved without actually moving")
    parser.add_argument("--no-backup", action="store_true", help="Skip creating backup")
    args = parser.parse_args()

    print("="*80)
    print("Repository Reorganization Script")
    print("="*80)

    if args.dry_run:
        print("\n🔍 DRY RUN MODE - No files will be moved\n")
    else:
        print("\n⚠️  ACTUAL MODE - Files will be moved!\n")
        response = input("Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Cancelled.")
            return

    # Step 1: Create backup
    backup_dir = None
    if not args.no_backup and not args.dry_run:
        backup_dir = create_backup(args.dry_run)

    # Step 2: Create folders
    print("\n📁 Creating folders...")
    create_folders(args.dry_run)

    # Step 3: Move files
    print("\n📦 Moving files...")
    moved, skipped, errors = move_files(args.dry_run, backup_dir)

    # Step 4: Generate report
    print("\n📄 Generating report...")
    generate_report(moved, skipped, errors, args.dry_run)

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Files moved: {len(moved)}")
    print(f"Files skipped: {len(skipped)}")
    print(f"Errors: {len(errors)}")

    if not args.dry_run:
        print(f"\n✓ Backup created at: {backup_dir}")
        print(f"✓ Report saved: REORGANIZATION_REPORT.md")
        print("\n✓ Repository reorganization complete!")
        print("\nNext steps:")
        print("1. Review REORGANIZATION_REPORT.md")
        print("2. Update any broken links in README.md")
        print("3. Test that scripts still work from new locations")
        print("4. Commit changes to git")
    else:
        print("\n✓ Dry run complete. Run without --dry-run to actually move files.")


if __name__ == "__main__":
    main()
