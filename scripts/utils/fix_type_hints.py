#!/usr/bin/env python3
"""Fix type hints in event source files."""

import re
from pathlib import Path

def fix_file(file_path: str, add_imports: bool = True) -> None:
    """Fix type hints in a single file.

    Args:
        file_path: Path to file to fix.
        add_imports: Whether to add missing imports.
    """
    path = Path(file_path)
    content = path.read_text()

    # Add imports if needed
    if add_imports:
        # Check if Callable and Awaitable are imported
        if "from typing import" in content:
            if "Callable" not in content or "Awaitable" not in content:
                # Find the typing import line
                pattern = r"(from typing import [^)]+)\)"
                match = re.search(pattern, content)
                if match:
                    old_import = match.group(0)
                    # Add Callable and Awaitable if missing
                    imports_set = set()
                    if "Callable" not in old_import:
                        imports_set.add("Callable")
                    if "Awaitable" not in old_import:
                        imports_set.add("Awaitable")

                    if imports_set:
                        # Extract existing imports
                        import_part = old_import[len("from typing import "):-1]
                        imports_list = [i.strip() for i in import_part.split(",")]
                        imports_list.extend(imports_set)
                        imports_list = sorted(set(imports_list))
                        new_import = f"from typing import {', '.join(imports_list)}"
                        content = content.replace(old_import, new_import)

    # Fix callback type hints
    # Pattern: def set_event_callback(self, callback) -> None:
    pattern = r"def set_event_callback\(self, callback\) -> None:"
    replacement = (
        "def set_event_callback(\n"
        "        self, callback: Callable[[Dict[str, Any], str], Awaitable[None]]\n"
        "    ) -> None:"
    )
    content = re.sub(pattern, replacement, content)

    # Write back
    path.write_text(content)
    print(f"Fixed: {file_path}")


# Files to fix
files_to_fix = [
    "components/event_sources/kafka_source.py",
    "components/event_sources/scol_source.py",
    "components/event_sources/s3_source.py",
    "components/event_sources/syslog_hec_source.py",
]

base_path = Path(".")

for file_name in files_to_fix:
    file_path = base_path / file_name
    if file_path.exists():
        fix_file(str(file_path))
    else:
        print(f"Not found: {file_path}")

print("\nDone fixing type hints!")
