#!/usr/bin/env python3
"""
check-css-coverage.py — Verify every className in JSX/TSX files has a CSS definition.

Usage:
  python3 check-css-coverage.py <css_file> <jsx_file_or_dir> [<jsx_file_or_dir> ...]

Examples:
  python3 check-css-coverage.py src/styles.css src/App.jsx src/components/
  python3 check-css-coverage.py src/styles.css src/

Scans .jsx, .tsx files for className="..." and className={`...`} tokens,
extracts all class names (including static parts of dynamic template literals),
then checks them against class selectors in the CSS file.

Exit code 0 = all covered, 1 = missing classes.
"""
import re
import sys
import os
from pathlib import Path


def find_jsx_files(paths):
    """Expand directories and filter to .jsx/.tsx files."""
    files = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            files.extend(path.rglob("*.jsx"))
            files.extend(path.rglob("*.tsx"))
        elif path.suffix in (".jsx", ".tsx"):
            files.append(path)
    # Exclude node_modules
    return [f for f in files if "node_modules" not in str(f)]


def extract_classnames(content):
    """Extract all className tokens from JSX/TSX content."""
    classes = set()
    
    # className="static classes"
    for m in re.finditer(r'className="([^"]+)"', content):
        for cls in m.group(1).split():
            classes.add(cls)
    
    # className={`template literal`}
    for m in re.finditer(r'className=\{`([^`]+)`\}', content):
        for cls in re.group(1).split():
            # Skip interpolation artifacts
            if "${" not in cls and "}" not in cls:
                classes.add(cls)
    
    # Dynamic template literals with ${...}
    for m in re.finditer(r'className=\{`([^`]*\$\{[^}]+\}[^`]*)`\}', content):
        # Extract static class names from the template
        static_parts = re.findall(r'\b([a-zA-Z][\w-]*)\b', m.group(1))
        # Skip JS keywords/variables that aren't class names
        skip = {
            'className', 'isActive', 'open', 'severity', 'category',
            'scope', 'type', 'String', 'severityKey', 'actionMsg',
            'batchMsg', 'amendmentResult', 'entry', 'meta', 'cls',
            'hasError', 'hasWarning', 'isBlocker', 'failed', 'length',
            'kind', 'success', 'issue', 'none', 'diff', 'alert',
        }
        for cls in static_parts:
            if cls not in skip:
                classes.add(cls)
    
    return classes


def extract_css_classes(css_content):
    """Extract all class names from CSS selectors."""
    classes = set()
    for m in re.finditer(r'\.([\w-]+)', css_content):
        classes.add(m.group(1))
    return classes


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    
    css_file = sys.argv[1]
    jsx_paths = sys.argv[2:]
    
    # Read CSS
    with open(css_file) as f:
        css_content = f.read()
    css_classes = extract_css_classes(css_content)
    
    # Collect all JSX class names
    jsx_files = find_jsx_files(jsx_paths)
    all_classes = set()
    
    for fpath in jsx_files:
        with open(fpath) as f:
            content = f.read()
        classes = extract_classnames(content)
        all_classes.update(classes)
    
    # Check coverage
    missing = sorted(all_classes - css_classes)
    covered = sorted(all_classes & css_classes)
    
    print(f"JSX files scanned: {len(jsx_files)}")
    print(f"CSS file: {css_file}")
    print(f"Total unique className tokens in JSX: {len(all_classes)}")
    print(f"Covered in CSS: {len(covered)}")
    print(f"Missing from CSS: {len(missing)}")
    
    if missing:
        print("\nMissing classes:")
        for c in missing:
            print(f"  .{c}")
        sys.exit(1)
    else:
        print("\n✓ All className tokens have CSS definitions.")
        sys.exit(0)


if __name__ == "__main__":
    main()