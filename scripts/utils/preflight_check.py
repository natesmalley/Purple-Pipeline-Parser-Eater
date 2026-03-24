#!/usr/bin/env python3
"""
Pre-Flight Validation Script for Production Conversion
Validates all system components before starting 165+ parser conversion
"""
import sys
import os
import subprocess
from pathlib import Path
import yaml
import json
from datetime import datetime

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


class PreFlightChecker:
    """Comprehensive pre-flight validation"""

    def __init__(self):
        self.checks_passed = 0
        self.checks_failed = 0
        self.warnings = 0
        self.results = []

    def print_header(self):
        """Print validation header"""
        print(f"\n{BOLD}{'='*80}{RESET}")
        print(f"{BOLD}{BLUE}Purple Pipeline Parser Eater - Pre-Flight Validation{RESET}")
        print(f"{BOLD}{'='*80}{RESET}\n")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print(f"Purpose: Validate system readiness for 165+ parser conversion\n")

    def check(self, name: str, passed: bool, details: str = "", warning: bool = False):
        """Record check result"""
        if passed:
            if warning:
                status = f"{YELLOW}[WARN]{RESET}"
                self.warnings += 1
            else:
                status = f"{GREEN}[PASS]{RESET}"
                self.checks_passed += 1
        else:
            status = f"{RED}[FAIL]{RESET}"
            self.checks_failed += 1

        print(f"{status} {name}")
        if details:
            print(f"      {details}")

        self.results.append({
            "name": name,
            "passed": passed,
            "warning": warning,
            "details": details
        })

    def section(self, title: str):
        """Print section header"""
        print(f"\n{BOLD}{'-'*80}{RESET}")
        print(f"{BOLD}{title}{RESET}")
        print(f"{BOLD}{'-'*80}{RESET}")

    def run_all_checks(self):
        """Run all pre-flight checks"""
        self.print_header()

        # 1. Environment & Dependencies
        self.section("1. Environment & Dependencies")
        self.check_python_version()
        self.check_required_packages()
        self.check_disk_space()
        self.check_memory()

        # 2. Docker & Milvus
        self.section("2. Docker & Milvus Vector Database")
        self.check_docker_installed()
        self.check_docker_running()
        self.check_milvus_container()
        self.check_milvus_connectivity()

        # 3. Configuration Files
        self.section("3. Configuration Files")
        self.check_config_file()
        self.check_environment_variables()

        # 4. Directory Structure
        self.section("4. Directory Structure")
        self.check_directories()
        self.check_observo_docs()

        # 5. API Connectivity
        self.section("5. API Connectivity")
        self.check_anthropic_api()
        self.check_observo_api()
        self.check_github_api()

        # 6. RAG Knowledge Base
        self.section("6. RAG Knowledge Base")
        self.check_rag_populated()

        # 7. System Components
        self.section("7. System Components")
        self.check_components_exist()

        # Print summary
        self.print_summary()

        return self.checks_failed == 0

    def check_python_version(self):
        """Check Python version >= 3.8"""
        version = sys.version_info
        passed = version.major == 3 and version.minor >= 8
        details = f"Python {version.major}.{version.minor}.{version.micro}"
        self.check("Python version >= 3.8", passed, details)

    def check_required_packages(self):
        """Check required Python packages"""
        required = [
            "anthropic", "aiohttp", "pyyaml", "pymilvus",
            "sentence_transformers", "torch", "tenacity"
        ]
        missing = []

        for package in required:
            try:
                __import__(package)
            except ImportError:
                missing.append(package)

        passed = len(missing) == 0
        details = f"Missing: {', '.join(missing)}" if missing else "All packages installed"
        self.check("Required Python packages", passed, details)

    def check_disk_space(self):
        """Check available disk space"""
        try:
            import shutil
            stat = shutil.disk_usage(Path.cwd())
            free_gb = stat.free / (1024**3)
            passed = free_gb >= 10
            warning = 10 <= free_gb < 20
            details = f"{free_gb:.1f} GB available (10 GB minimum required)"
            self.check("Disk space", passed or warning, details, warning=warning)
        except Exception as e:
            self.check("Disk space", False, f"Error: {e}")

    def check_memory(self):
        """Check available memory"""
        try:
            import psutil
            mem = psutil.virtual_memory()
            available_gb = mem.available / (1024**3)
            passed = available_gb >= 4
            warning = 4 <= available_gb < 8
            details = f"{available_gb:.1f} GB available (8 GB recommended)"
            self.check("Available memory", passed or warning, details, warning=warning)
        except ImportError:
            self.check("Available memory", True, "psutil not installed, skipping", warning=True)
        except Exception as e:
            self.check("Available memory", False, f"Error: {e}")

    def check_docker_installed(self):
        """Check if Docker is installed"""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            passed = result.returncode == 0
            details = result.stdout.strip() if passed else "Docker not found"
            self.check("Docker installed", passed, details)
        except Exception as e:
            self.check("Docker installed", False, f"Error: {e}")

    def check_docker_running(self):
        """Check if Docker daemon is running"""
        try:
            result = subprocess.run(
                ["docker", "ps"],
                capture_output=True,
                text=True,
                timeout=5
            )
            passed = result.returncode == 0
            details = "Docker daemon running" if passed else "Docker daemon not running"
            self.check("Docker daemon", passed, details)
        except Exception as e:
            self.check("Docker daemon", False, f"Error: {e}")

    def check_milvus_container(self):
        """Check if Milvus container is running"""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=milvus", "--format", "{{.Names}}\t{{.Status}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            passed = "milvus" in result.stdout.lower() and "up" in result.stdout.lower()
            details = result.stdout.strip() if result.stdout else "Milvus container not running"
            self.check("Milvus container", passed, details)
        except Exception as e:
            self.check("Milvus container", False, f"Error: {e}")

    def check_milvus_connectivity(self):
        """Check if Milvus is accessible"""
        try:
            from pymilvus import connections, utility
            connections.connect(host="localhost", port="19530", timeout=5)
            version = utility.get_server_version()
            connections.disconnect("default")
            self.check("Milvus connectivity", True, f"Milvus v{version}")
        except Exception as e:
            self.check("Milvus connectivity", False, f"Cannot connect: {e}")

    def check_config_file(self):
        """Check if config.yaml exists and is valid"""
        config_path = Path("config.yaml")
        if not config_path.exists():
            self.check("config.yaml exists", False, "File not found")
            return

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)

            required_sections = ['anthropic', 'observo', 'processing', 'milvus']
            missing = [s for s in required_sections if s not in config]

            passed = len(missing) == 0
            details = f"Missing sections: {', '.join(missing)}" if missing else "All sections present"
            self.check("config.yaml valid", passed, details)
        except Exception as e:
            self.check("config.yaml valid", False, f"Parse error: {e}")

    def check_environment_variables(self):
        """Check required environment variables"""
        required = {
            "ANTHROPIC_API_KEY": "Claude API key",
        }
        optional = {
            "OBSERVO_API_KEY": "Observo.ai API key (or dry-run mode)",
            "GITHUB_TOKEN": "GitHub token (optional)",
            "WEB_UI_AUTH_TOKEN": "Web UI auth token (optional)"
        }

        # Check required
        for var, desc in required.items():
            value = os.environ.get(var)
            passed = bool(value and value not in ["your-key-here", ""])
            details = desc
            self.check(f"Env var: {var}", passed, details)

        # Check optional
        for var, desc in optional.items():
            value = os.environ.get(var)
            has_value = bool(value and value not in ["your-key-here", ""])
            details = f"{desc} - {'Set' if has_value else 'Not set (optional)'}"
            self.check(f"Env var: {var}", True, details, warning=not has_value)

    def check_directories(self):
        """Check required directories"""
        required_dirs = [
            "components",
            "utils",
            "output",
            "observo docs"
        ]

        for dirname in required_dirs:
            dir_path = Path(dirname)
            passed = dir_path.exists() and dir_path.is_dir()
            details = "Exists" if passed else "Missing"
            self.check(f"Directory: {dirname}/", passed, details)

    def check_observo_docs(self):
        """Check Observo documentation files"""
        docs_dir = Path("observo docs")
        if not docs_dir.exists():
            self.check("Observo docs", False, "Directory not found")
            return

        doc_files = list(docs_dir.glob("*.md"))
        passed = len(doc_files) >= 10
        details = f"{len(doc_files)} documentation files found (10+ expected)"
        self.check("Observo docs", passed, details)

    def check_anthropic_api(self):
        """Check Anthropic API connectivity"""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key or api_key in ["your-key-here", "", "${ANTHROPIC_API_KEY}"]:
            self.check("Anthropic API", False, "API key not set")
            return

        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=api_key, timeout=10.0)
            # Simple API test - just check if we can create client
            # Don't make actual API call to save costs
            passed = True
            details = "API key configured (not tested to avoid costs)"
            self.check("Anthropic API", passed, details, warning=True)
        except Exception as e:
            self.check("Anthropic API", False, f"Error: {e}")

    def check_observo_api(self):
        """Check Observo.ai API connectivity"""
        # SECURITY NOTE: "dry-run-mode" is a special value indicating test mode, not a credential
        DRY_RUN_MODE_VALUE = "dry-run-mode"  # Special test mode indicator, not a credential
        api_key = os.environ.get("OBSERVO_API_KEY", DRY_RUN_MODE_VALUE)

        if api_key in ["your-key-here", "", "${OBSERVO_API_KEY}"]:
            self.check("Observo.ai API", True, "Not configured - will use dry-run mode", warning=True)
        elif api_key == DRY_RUN_MODE_VALUE:
            self.check("Observo.ai API", True, "Dry-run mode enabled", warning=True)
        else:
            # Don't test actual API to avoid unnecessary calls
            self.check("Observo.ai API", True, "API key configured", warning=True)

    def check_github_api(self):
        """Check GitHub API connectivity"""
        token = os.environ.get("GITHUB_TOKEN", "")

        if not token or token in ["your-token-here", "${GITHUB_TOKEN}"]:
            self.check("GitHub API", True, "Not configured - will use public API (rate limited)", warning=True)
        else:
            self.check("GitHub API", True, "Token configured", warning=True)

    def check_rag_populated(self):
        """Check if RAG knowledge base is populated"""
        try:
            from pymilvus import connections, Collection
            connections.connect(host="localhost", port="19530", timeout=5)

            try:
                collection = Collection("observo_knowledge")
                count = collection.num_entities
                passed = count >= 100
                warning = 0 < count < 100
                details = f"{count} documents in RAG (100+ expected)"
                self.check("RAG knowledge base", passed or warning, details, warning=warning)
            except (AttributeError, KeyError, RuntimeError, ValueError) as e:
                self.check("RAG knowledge base", False, f"Collection not found or invalid - run: python ingest_observo_docs.py ({e})")

            connections.disconnect("default")
        except Exception as e:
            self.check("RAG knowledge base", False, f"Cannot check: {e}")

    def check_components_exist(self):
        """Check that all required components exist"""
        required_files = [
            "orchestrator.py",
            "main.py",
            "components/github_scanner.py",
            "components/claude_analyzer.py",
            "components/observo_client.py",
            "components/rag_knowledge.py",
            "components/pipeline_validator.py",
            "components/parser_output_manager.py"
        ]

        missing = []
        for filepath in required_files:
            if not Path(filepath).exists():
                missing.append(filepath)

        passed = len(missing) == 0
        details = f"Missing: {', '.join(missing)}" if missing else "All components present"
        self.check("System components", passed, details)

    def print_summary(self):
        """Print validation summary"""
        print(f"\n{BOLD}{'='*80}{RESET}")
        print(f"{BOLD}Pre-Flight Validation Summary{RESET}")
        print(f"{BOLD}{'='*80}{RESET}\n")

        total = self.checks_passed + self.checks_failed
        print(f"  Total checks: {total}")
        print(f"  {GREEN}Passed: {self.checks_passed}{RESET}")
        print(f"  {RED}Failed: {self.checks_failed}{RESET}")
        print(f"  {YELLOW}Warnings: {self.warnings}{RESET}")

        success_rate = (self.checks_passed / total * 100) if total > 0 else 0
        print(f"\n  Success rate: {success_rate:.1f}%")

        print(f"\n{BOLD}{'='*80}{RESET}")

        if self.checks_failed == 0:
            print(f"\n{GREEN}{BOLD}[OK] PRE-FLIGHT VALIDATION PASSED{RESET}")
            print(f"{GREEN}System is ready for production conversion!{RESET}\n")

            if self.warnings > 0:
                print(f"{YELLOW}Note: {self.warnings} warnings detected - review above{RESET}\n")

            print("Next steps:")
            print("  1. Start Milvus: docker-compose up -d")
            print("  2. Populate RAG: python ingest_observo_docs.py")
            print("  3. Start conversion: python main.py --max-parsers 10 --verbose")
            return True
        else:
            print(f"\n{RED}{BOLD}[FAIL] PRE-FLIGHT VALIDATION FAILED{RESET}")
            print(f"{RED}System is NOT ready - fix {self.checks_failed} failed checks{RESET}\n")

            print("Failed checks:")
            for result in self.results:
                if not result["passed"] and not result["warning"]:
                    print(f"  - {result['name']}")
                    if result["details"]:
                        print(f"    {result['details']}")
            return False


def main():
    """Main entry point"""
    checker = PreFlightChecker()

    try:
        success = checker.run_all_checks()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Pre-flight check interrupted by user{RESET}")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n{RED}Fatal error during pre-flight check: {e}{RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
