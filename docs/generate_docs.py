#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pydoc-markdown>=4.8.0,<5.0.0",
# ]
# ///
"""
Self-contained script to generate SDK documentation using pydoc-markdown.

Run with: uv run generate_docs.py
"""

import sys
from pathlib import Path

# Get script directory and project root
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
SDK_PATH = PROJECT_ROOT / "sdk" / "python"
OUTPUT_DIR = SCRIPT_DIR / "docs" / "sdk"

# Add the SDK to Python path
sys.path.insert(0, str(SDK_PATH))

from pydoc_markdown import PydocMarkdown
from pydoc_markdown.contrib.loaders.python import PythonLoader
from pydoc_markdown.contrib.renderers.markdown import MarkdownRenderer
from pydoc_markdown.contrib.processors.filter import FilterProcessor
from pydoc_markdown.contrib.processors.smart import SmartProcessor
from pydoc_markdown.contrib.processors.crossref import CrossrefProcessor


def clean_code_examples(text):
    """
    Convert doctest-style examples into proper code blocks without markers.

    Args:
        text: Markdown text content

    Returns:
        str: Text with cleaned code examples
    """
    import re

    lines = text.split("\n")
    result = []
    in_code_block = False
    in_doctest = False
    doctest_lines = []
    indent_level = 0

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check for code block markers
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            result.append(line)
            i += 1
            continue

        if in_code_block:
            # Inside a code block - leave as is
            result.append(line)
            i += 1
            continue

        # Check for doctest markers (>>> or ...)
        if re.match(r"^(\s*)>>>\s", line):
            if not in_doctest:
                # Start of a doctest block
                in_doctest = True
                indent_level = len(re.match(r"^(\s*)", line).group(1))
                # Add code block marker
                result.append(" " * indent_level + "```python")

            # Remove >>> marker
            cleaned = re.sub(r"^(\s*)>>>\s?", r"\1", line)
            doctest_lines.append(cleaned)
            i += 1
            continue

        elif re.match(r"^(\s*)\.\.\.\s", line) and in_doctest:
            # Continuation line in doctest
            cleaned = re.sub(r"^(\s*)\.\.\.\s?", r"\1", line)
            doctest_lines.append(cleaned)
            i += 1
            continue

        elif in_doctest:
            # End of doctest block
            # Flush collected doctest lines
            result.extend(doctest_lines)
            result.append(" " * indent_level + "```")
            result.append("")  # Add blank line after code block
            doctest_lines = []
            in_doctest = False

            # Process current line normally
            result.append(line)
            i += 1
            continue

        # Normal line
        result.append(line)
        i += 1

    # Handle case where doctest block is at the end
    if in_doctest:
        result.extend(doctest_lines)
        result.append(" " * indent_level + "```")

    return "\n".join(result)


def escape_mdx_syntax(text):
    """
    Escape MDX special characters that cause parsing issues.

    Args:
        text: Markdown text content

    Returns:
        str: Text with MDX-safe escaping
    """
    import re

    # Split by code blocks to handle them separately
    parts = []
    in_code_block = False
    lines = text.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check for code block markers
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            parts.append(line)
        elif in_code_block:
            # Inside code block - don't escape
            parts.append(line)
        else:
            # Outside code block - escape only curly braces in non-code text
            # Don't escape underscores - they're fine in Markdown/MDX
            escaped_line = line

            # Find inline code segments
            inline_code_pattern = r"`[^`]+`"
            inline_codes = re.findall(inline_code_pattern, line)

            # Temporarily replace inline code with placeholders
            temp_line = line
            for idx, code in enumerate(inline_codes):
                temp_line = temp_line.replace(code, f"__INLINE_CODE_{idx}__", 1)

            # Escape only curly braces in non-code text
            temp_line = temp_line.replace("{", "\\{").replace("}", "\\}")

            # Restore inline code
            for idx, code in enumerate(inline_codes):
                temp_line = temp_line.replace(f"__INLINE_CODE_{idx}__", code, 1)

            parts.append(temp_line)

        i += 1

    return "\n".join(parts)


def should_include_item(item):
    """
    Filter function to determine if an item should be included in docs.

    Args:
        item: The documentation item (class, function, etc.)

    Returns:
        bool: True if item should be included, False otherwise
    """
    # Exclude items starting with underscore (private)
    if item.name.startswith("_"):
        return False

    # Exclude abstract base classes
    if hasattr(item, "bases"):
        for base in item.bases:
            if (
                "ABC" in str(base)
                or "Abstract" in item.name
                or item.name.endswith("Base")
            ):
                return False

    # Exclude specific patterns (add more as needed)
    exclude_patterns = ["Base", "Abstract", "Mixin"]
    if any(pattern in item.name for pattern in exclude_patterns):
        return False

    return True


def generate_docs():
    """Generate documentation for all modules."""

    print("=" * 60)
    print("SDK Documentation Generator")
    print("=" * 60)
    print()
    print(f"Script location: {SCRIPT_DIR}")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"SDK path: {SDK_PATH}")
    print()

    # Output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✓ Output directory: {OUTPUT_DIR}")
    print()

    # Modules to document organized by category
    # Format: "category": {"module.path": ("output-subdir", "file-name")}
    modules = {
        "API": {
            "luml.api._client": ("api", "client"),
            "luml.api.resources.bucket_secrets": ("api", "bucket-secrets"),
            "luml.api.resources.collections": ("api", "collections"),
            "luml.api.resources.model_artifacts": ("api", "model-artifacts"),
            "luml.api.resources.orbits": ("api", "orbits"),
            "luml.api.resources.organizations": ("api", "organizations"),
        },
        "Experiments": {
            "luml.experiments.tracker": ("experiments", "tracker"),
        },
        "Integrations": {
            "luml.integrations.sklearn.packaging": ("integrations", "sklearn"),
            "luml.integrations.langgraph.packaging": ("integrations", "langgraph"),
        },
    }

    all_generated_files = []

    for category, category_modules in modules.items():
        print(f"\n{category}")
        print("-" * 60)

        for module_name, (subdir, file_name) in category_modules.items():
            print(f"→ Processing {module_name}...")

            try:
                # Configure pydoc-markdown
                session = PydocMarkdown()

                # Set up loader
                loader = PythonLoader(
                    search_path=[str(SDK_PATH)], modules=[module_name]
                )
                session.loaders = [loader]

                # Set up processors with filters
                session.processors = [
                    FilterProcessor(
                        expression="not name.startswith('_') and default()",
                        skip_empty_modules=True,
                    ),
                    SmartProcessor(),
                    CrossrefProcessor(),
                ]

                # Set up renderer
                session.renderer = MarkdownRenderer()

                # Load and process modules
                modules_data = session.load_modules()

                if not modules_data:
                    print(f"  ✗ No data found for {module_name}")
                    continue

                # Filter out unwanted items
                for module in modules_data:
                    module.members = [
                        m for m in module.members if should_include_item(m)
                    ]

                # Render documentation
                session.process(modules_data)
                output = session.renderer.render_to_string(modules_data)

                # Clean code examples (remove doctest markers)
                output = clean_code_examples(output)

                # Unescape underscores in headers (pydoc-markdown escapes them unnecessarily)
                output = output.replace("\\_", "_")

                # Escape MDX syntax
                output = escape_mdx_syntax(output)

                # Create subdirectory and write file
                subdir_path = OUTPUT_DIR / subdir
                subdir_path.mkdir(parents=True, exist_ok=True)

                output_file = subdir_path / f"{file_name}.md"
                output_file.write_text(output)
                all_generated_files.append(output_file)
                print(f"  ✓ Generated {subdir}/{file_name}.md")

            except Exception as e:
                print(f"  ✗ Error: {e}")
                continue

    print()
    print("=" * 60)

    # List generated files
    if all_generated_files:
        print(
            f"Successfully generated {len(all_generated_files)} documentation file(s):"
        )
        # Group by subdirectory
        by_subdir = {}
        for file in all_generated_files:
            subdir = file.parent.name
            if subdir not in by_subdir:
                by_subdir[subdir] = []
            by_subdir[subdir].append(file.name)

        for subdir in sorted(by_subdir.keys()):
            print(f"\n  {subdir}/")
            for filename in sorted(by_subdir[subdir]):
                print(f"    - {filename}")
    else:
        print("No documentation files were generated")

    print("=" * 60)


if __name__ == "__main__":
    generate_docs()
