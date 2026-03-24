#!/usr/bin/env python3
"""
Script to fix relative imports across all component files
"""
import re
from pathlib import Path

def fix_imports_in_file(file_path: Path):
    """Fix relative imports in a single file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern to match: from ..utils.something import ...
    pattern = r'from \.\.utils\.(\w+) import (.+)'

    # Check if pattern exists
    if not re.search(pattern, content):
        print(f"[OK] {file_path.name} - No relative imports found")
        return False

    # Replace with try/except pattern
    def replacement(match):
        module = match.group(1)
        imports = match.group(2)
        return f"""# Use absolute imports for proper module execution
try:
    from utils.{module} import {imports}
except ImportError:
    from ..utils.{module} import {imports}"""

    new_content = re.sub(pattern, replacement, content)

    # Write back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"[OK] {file_path.name} - Fixed relative imports")
    return True

def main():
    """Fix all component files"""
    components_dir = Path(__file__).parent / 'components'

    print("Fixing relative imports in component files...")
    print("=" * 60)

    fixed_count = 0
    for py_file in components_dir.glob('*.py'):
        if py_file.name == '__init__.py':
            continue

        if fix_imports_in_file(py_file):
            fixed_count += 1

    print("=" * 60)
    print(f"[OK] Fixed {fixed_count} files")
    print("Import fix complete!")

if __name__ == "__main__":
    main()
