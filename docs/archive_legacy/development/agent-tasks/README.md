# Agent Task Prompts - Large File Refactoring

This directory contains detailed, self-contained prompts for Claude Haiku agents to perform large-scale code refactoring tasks safely and efficiently.

---

## Overview

**Purpose:** Break down 3 large monolithic files (3,186 total lines) into smaller, focused, maintainable modules

**Total Work:** 3 agents, ~300 minutes of agent time, ~20 new modules created

**Benefits:**
- Improved code maintainability
- Easier testing and debugging
- Better separation of concerns
- Reduced cognitive load for developers
- More modular, reusable code

---

## Agent Tasks

### Agent 1: Refactor Web Feedback UI
**File:** `AGENT_1_REFACTOR_WEB_FEEDBACK_UI.md`
**Target:** `components/web_feedback_ui.py` (1,481 lines)
**Output:** `components/web_ui/` (7 modules)
**Time:** ~90 minutes
**Risk:** Medium

**Modules Created:**
- `components/web_ui/__init__.py` - Public interface
- `components/web_ui/app.py` - Flask app initialization
- `components/web_ui/auth.py` - Authentication decorator
- `components/web_ui/security.py` - Security headers, CORS, rate limiting
- `components/web_ui/routes.py` - All route handlers
- `components/web_ui/api_docs_integration.py` - API docs registration
- `components/web_ui/server.py` - Main server class

---

### Agent 2: Refactor Orchestrator
**File:** `AGENT_2_REFACTOR_ORCHESTRATOR.md`
**Target:** `orchestrator.py` (830 lines)
**Output:** `orchestrator/` (9 modules)
**Time:** ~120 minutes
**Risk:** Medium-High

**Modules Created:**
- `orchestrator/__init__.py` - Public interface
- `orchestrator/core.py` - Main orchestrator class
- `orchestrator/config.py` - Configuration loading
- `orchestrator/initializer.py` - Component initialization
- `orchestrator/phase_1_scanner.py` - Parser scanning
- `orchestrator/phase_2_analyzer.py` - Parser analysis
- `orchestrator/phase_3_generator.py` - Lua generation
- `orchestrator/phase_4_deployer.py` - Deployment
- `orchestrator/phase_5_reporter.py` - Report generation
- `orchestrator/utils.py` - Utility functions

---

### Agent 3: Refactor Observo API Client
**File:** `AGENT_3_REFACTOR_OBSERVO_API_CLIENT.md`
**Target:** `components/observo_api_client.py` (875 lines)
**Output:** `components/observo/` (8 modules)
**Time:** ~90 minutes
**Risk:** Medium

**Modules Created:**
- `components/observo/__init__.py` - Public interface
- `components/observo/client.py` - Base HTTP client
- `components/observo/exceptions.py` - Custom exceptions
- `components/observo/pipelines.py` - Pipeline operations
- `components/observo/sources.py` - Source operations
- `components/observo/sinks.py` - Sink operations
- `components/observo/transforms.py` - Transform operations
- `components/observo/monitoring.py` - Monitoring & health

---

## How to Execute

### Option 1: Using Claude Code CLI

**Execute all agents in sequence:**

```bash
# Agent 1 - Web UI refactoring
claude-code task --file=.agent-tasks/AGENT_1_REFACTOR_WEB_FEEDBACK_UI.md --model=haiku

# Verify Agent 1 completed successfully, then:

# Agent 2 - Orchestrator refactoring
claude-code task --file=.agent-tasks/AGENT_2_REFACTOR_ORCHESTRATOR.md --model=haiku

# Verify Agent 2 completed successfully, then:

# Agent 3 - Observo API refactoring
claude-code task --file=.agent-tasks/AGENT_3_REFACTOR_OBSERVO_API_CLIENT.md --model=haiku
```

### Option 2: Using Task Tool in Claude Code

Within a Claude Code session:

```python
# Execute Agent 1
Task(
    subagent_type="general-purpose",
    description="Refactor web_feedback_ui.py",
    prompt=open('.agent-tasks/AGENT_1_REFACTOR_WEB_FEEDBACK_UI.md').read(),
    model="haiku"
)

# After verification, execute Agent 2
Task(
    subagent_type="general-purpose",
    description="Refactor orchestrator.py",
    prompt=open('.agent-tasks/AGENT_2_REFACTOR_ORCHESTRATOR.md').read(),
    model="haiku"
)

# After verification, execute Agent 3
Task(
    subagent_type="general-purpose",
    description="Refactor observo_api_client.py",
    prompt=open('.agent-tasks/AGENT_3_REFACTOR_OBSERVO_API_CLIENT.md').read(),
    model="haiku"
)
```

### Option 3: Manual Execution

**Read each prompt file and execute the steps manually, following the detailed instructions.**

---

## Execution Order

**IMPORTANT:** Execute in this specific order:

1. **Agent 1 first** (Web UI) - Most isolated, lowest risk
2. **Verify Agent 1** - Run tests, check imports
3. **Agent 3 second** (Observo API) - Moderate coupling
4. **Verify Agent 3** - Run tests, check imports
5. **Agent 2 last** (Orchestrator) - Core component, highest risk
6. **Verify Agent 2** - Run tests, check imports
7. **Final verification** - Run all tests, Snyk scan

**Rationale:** Start with least risky, build confidence before tackling core orchestrator

---

## Verification After Each Agent

Run these checks after each agent completes:

### 1. Syntax Check
```bash
python -m py_compile <new_directory>/*.py
```

### 2. Import Check
```python
# For Agent 1
from components.web_ui import WebFeedbackServer
from components.web_feedback_ui import WebFeedbackServer  # Old path

# For Agent 2
from orchestrator import ConversionSystemOrchestrator
import orchestrator  # Old path

# For Agent 3
from components.observo import ObservoAPI
from components.observo_api_client import ObservoAPI  # Old path
```

### 3. Entry Point Check
```bash
python main.py --help
python continuous_conversion_service.py --help
```

### 4. Module Size Check
```bash
wc -l <new_directory>/*.py
# Verify all files <400 lines
```

---

## Rollback Procedures

### Per-Agent Rollback

**If Agent 1 fails:**
```bash
git checkout -- components/web_feedback_ui.py
rm -rf components/web_ui/
```

**If Agent 2 fails:**
```bash
git checkout -- orchestrator.py
rm -rf orchestrator/
```

**If Agent 3 fails:**
```bash
git checkout -- components/observo_api_client.py
rm -rf components/observo/
```

### Full Rollback

```bash
# Discard all changes
git reset --hard HEAD

# Or revert specific commits
git revert <commit-hash>
```

---

## Expected Outcomes

### Before Refactoring
```
components/web_feedback_ui.py       1,481 lines
orchestrator.py                       830 lines
components/observo_api_client.py      875 lines
-------------------------------------------
Total:                              3,186 lines (3 files)
```

### After Refactoring
```
components/web_ui/                  ~1,350 lines (7 modules)
orchestrator/                       ~1,030 lines (9 modules)
components/observo/                 ~  875 lines (8 modules)
-------------------------------------------
Total:                              ~3,255 lines (24 modules)
Average module size:                  ~136 lines
```

**Net Result:**
- 3 monolithic files → 24 focused modules
- Average file size: 1,062 lines → 136 lines (87% reduction)
- All functionality preserved
- 100% backward compatible
- Zero breaking changes

---

## Testing Requirements

### After All Agents Complete

**1. Run Full Test Suite:**
```bash
pytest tests/ -v --tb=short
```

**2. Run Snyk Security Scan:**
```bash
snyk code test --severity-threshold=high
```

**3. Manual Testing:**
- Start continuous_conversion_service.py
- Access web UI
- Test one complete conversion workflow
- Verify all 5 phases execute

**4. Integration Testing:**
- Test main.py CLI
- Test individual service scripts
- Verify all components integrate correctly

---

## Success Criteria

**All 3 agents must achieve:**

- [ ] No syntax errors introduced
- [ ] All imports resolve correctly
- [ ] All tests pass
- [ ] No new Snyk vulnerabilities
- [ ] Entry points work unchanged
- [ ] Backward compatibility maintained
- [ ] Average module size <300 lines
- [ ] All functionality preserved

---

## Support & Troubleshooting

### Common Issues

**Issue: Import errors after refactoring**
- Check __init__.py files are correct
- Verify all imports use correct paths
- Check for circular imports

**Issue: Tests failing**
- Update test imports if needed
- Verify mocks still work
- Check fixtures are compatible

**Issue: Runtime errors**
- Check async/await preserved
- Verify all decorators intact
- Check Flask routes registered

### Getting Help

If agents encounter issues:
1. Review the agent's output for errors
2. Check syntax with `python -m py_compile`
3. Test imports manually
4. Consult rollback instructions
5. Report issues in REFACTORING_ISSUES.md

---

## Notes

**Agent Capabilities:**
- Each prompt is self-contained
- Agents have full context needed
- Verification steps included
- Rollback instructions provided
- Safety checks at each step

**Important:**
- Execute agents sequentially, not in parallel
- Verify each agent before starting next
- Don't skip verification steps
- Keep original files until all verified
- Commit after each successful agent

---

**Document Version:** 1.0
**Created:** 2025-11-09
**Status:** READY FOR EXECUTION
**Last Updated:** 2025-11-09

---

## Quick Start

```bash
# 1. Read Agent 1 prompt
cat .agent-tasks/AGENT_1_REFACTOR_WEB_FEEDBACK_UI.md

# 2. Execute Agent 1 (using Task tool or manually)
# ... wait for completion ...

# 3. Verify Agent 1
pytest tests/ -k web_ui

# 4. Read Agent 2 prompt
cat .agent-tasks/AGENT_2_REFACTOR_ORCHESTRATOR.md

# 5. Execute Agent 2
# ... wait for completion ...

# 6. Verify Agent 2
python main.py --help

# 7. Read Agent 3 prompt
cat .agent-tasks/AGENT_3_REFACTOR_OBSERVO_API_CLIENT.md

# 8. Execute Agent 3
# ... wait for completion ...

# 9. Final verification
pytest tests/ -v
snyk code test
```

---

**End of README**
