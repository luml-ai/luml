#!/usr/bin/env python3
"""
Engine for generating SDK reference docs with pydoc-markdown.

This module holds the rendering pipeline: pydoc-markdown session setup and the
Markdown post-processing passes (signature formatting, doctest conversion,
MDX escaping, ...). It renders one module at a time via
`render_module_markdown`, or a whole source folder via `generate_docs`.

The repository entrypoint that knows which modules go to which docs pages is
`generate_docs.py` next to this file.
"""

import sys
import argparse
from pathlib import Path

try:
    from pydoc_markdown import PydocMarkdown
    from pydoc_markdown.contrib.loaders.python import PythonLoader
    from pydoc_markdown.contrib.processors.crossref import CrossrefProcessor
    from pydoc_markdown.contrib.processors.filter import FilterProcessor
    from pydoc_markdown.contrib.processors.smart import SmartProcessor
    from pydoc_markdown.contrib.renderers.markdown import MarkdownRenderer
except ImportError:
    print("✗ pydoc-markdown not found. Install it with:")
    print("   pip install pydoc-markdown")
    sys.exit(1)


def format_function_signatures(text):
    """
    Reformat function signatures to a consistent, readable style.

    - If <= 3 params and fits in 80 chars: single line
    - Otherwise: each parameter on its own line

    Example output for many params:
        @decorator
        def func(
                param1: str,
                param2: int,
                param3: dict,
                param4: list
        ) -> ReturnType

    Args:
        text: Markdown text content

    Returns:
        str: Text with reformatted signatures
    """
    import re

    lines = text.split("\n")
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if we're starting a code block with a function signature
        if line.strip() == "```python":
            result.append(line)
            i += 1

            # Collect lines until end of code block
            code_lines = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1

            # Process the code block content
            code_content = "\n".join(code_lines)

            # Check if this is a PURE function signature (not a code example)
            # Signatures: only decorators + function def, no body code
            # Examples: have function bodies, variable assignments, etc.
            is_signature_block = False
            if re.search(r"(^@|\bdef\s|\basync\s+def\s)", code_content, re.MULTILINE):
                # Check it's NOT an example (no function body, no assignments, etc.)
                # Signature blocks end with ) or ) -> Type, not with : followed by code
                code_content.strip()
                # If it has = outside of default params, or ends with : followed by body, it's example
                has_body = bool(
                    re.search(r":\s*\n\s+\S", code_content)
                )  # : followed by indented body
                has_assignments = bool(
                    re.search(r"^\s*\w+\s*=\s*[^=]", code_content, re.MULTILINE)
                )  # var = value
                has_function_calls = bool(
                    re.search(r"\w+\.\w+\(", code_content)
                )  # method calls like luml.foo()

                # It's a signature if it has no body/assignments/calls
                is_signature_block = (
                    not has_body and not has_assignments and not has_function_calls
                )

            if is_signature_block:
                # Normalize the signature - join lines and clean up whitespace
                # First, join all lines
                single_line = " ".join(code_content.split())

                # Extract decorators and function definition
                parts = []

                # Find all decorators
                decorator_pattern = r"@\w+(?:\.\w+)*(?:\([^)]*\))?"
                for match in re.finditer(decorator_pattern, single_line):
                    parts.append(match.group())

                # Find function definition
                func_match = re.search(
                    r"(async\s+)?def\s+(\w+)\s*\(([^)]*)\)\s*(->\s*[^:]+)?", single_line
                )

                if func_match:
                    is_async = func_match.group(1) or ""
                    func_name = func_match.group(2)
                    params_str = func_match.group(3).strip()
                    return_type = func_match.group(4) or ""

                    # Clean up return type spacing
                    if return_type:
                        return_type = re.sub(r"\s*->\s*", " -> ", return_type).strip()
                        return_type = " " + return_type

                    # Parse parameters into a list
                    param_list = []
                    if params_str:
                        # Split by comma, but handle nested brackets
                        depth = 0
                        current_param = []
                        for char in params_str:
                            if char in "([{":
                                depth += 1
                                current_param.append(char)
                            elif char in ")]}":
                                depth -= 1
                                current_param.append(char)
                            elif char == "," and depth == 0:
                                param_list.append("".join(current_param).strip())
                                current_param = []
                            else:
                                current_param.append(char)
                        if current_param:
                            param_list.append("".join(current_param).strip())

                    # Clean up each parameter
                    clean_params = []
                    for param in param_list:
                        param = re.sub(r"\s+", " ", param)
                        param = re.sub(r"\s*:\s*", ": ", param)
                        param = re.sub(r"\s*=\s*", " = ", param)
                        clean_params.append(param)

                    # Build the formatted signature
                    for decorator in parts:
                        result.append(decorator)

                    # Calculate signature length for single line
                    params_joined = ", ".join(clean_params)
                    signature = (
                        f"{is_async}def {func_name}({params_joined}){return_type}"
                    )

                    # Use multi-line if > 3 params OR line too long
                    if len(clean_params) <= 3 and len(signature) <= 80:
                        # Fits on one line
                        result.append(signature)
                    else:
                        # Multi-line format - each param on its own line
                        result.append(f"{is_async}def {func_name}(")
                        for j, param in enumerate(clean_params):
                            comma = "," if j < len(clean_params) - 1 else ""
                            result.append(f"        {param}{comma}")
                        result.append(f"){return_type}")
                else:
                    # Couldn't parse, keep original
                    result.extend(code_lines)
            else:
                # Not a function signature, keep original
                result.extend(code_lines)

            # Add closing code block marker
            if i < len(lines):
                result.append(lines[i])
        else:
            result.append(line)

        i += 1

    return "\n".join(result)


def dedent_code_blocks(text):
    """
    Remove extra indentation from code blocks.

    Code blocks from docstrings often have extra indentation that should be removed.

    Args:
        text: Markdown text content

    Returns:
        str: Text with dedented code blocks
    """
    lines = text.split("\n")
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Check if this is start of a code block
        if stripped.startswith("```"):
            # Collect the code block
            code_block_lines = [line]
            i += 1

            while i < len(lines):
                code_block_lines.append(lines[i])
                if lines[i].strip().startswith("```") and len(lines[i].strip()) <= 3:
                    break
                i += 1

            # Find minimum indentation of the block markers
            opening_indent = len(code_block_lines[0]) - len(
                code_block_lines[0].lstrip()
            )
            if len(code_block_lines) > 1:
                closing_indent = len(code_block_lines[-1]) - len(
                    code_block_lines[-1].lstrip()
                )
                min_indent = min(opening_indent, closing_indent)
            else:
                min_indent = opening_indent

            # Remove the common indentation from all lines
            for block_line in code_block_lines:
                if block_line.strip():  # Non-empty line
                    # Remove up to min_indent spaces
                    if (
                        len(block_line) >= min_indent
                        and block_line[:min_indent].strip() == ""
                    ):
                        result.append(block_line[min_indent:])
                    else:
                        result.append(block_line)
                else:
                    result.append(block_line)
        else:
            result.append(line)

        i += 1

    return "\n".join(result)


def join_split_string_assignments(text):
    """
    Join code-block assignments whose string value was split for docstring width.

    Some docstrings have examples like:
        bucket_location =
        "long/path/part-1
        part-2"

    In generated docs that should be a single copyable assignment line.

    Args:
        text: Markdown text content

    Returns:
        str: Text with split string assignments joined inside Python code blocks
    """
    import re

    def process_python_lines(code_lines):
        result = []
        i = 0

        while i < len(code_lines):
            line = code_lines[i]
            assignment_match = re.match(r"^(\s*[A-Za-z_]\w*)\s*=\s*$", line)

            if assignment_match and i + 1 < len(code_lines):
                first_value_line = code_lines[i + 1].strip()
                string_match = re.match(r"^([rRuUbBfF]*)(['\"])(.*)$", first_value_line)

                if string_match and not first_value_line.startswith(("'''", '"""')):
                    prefix = string_match.group(1)
                    quote = string_match.group(2)
                    first_content = string_match.group(3)
                    parts = []
                    j = i + 1
                    current_content = first_content
                    found_closing_quote = False

                    while j < len(code_lines):
                        if j > i + 1:
                            current_content = code_lines[j].strip()

                        if current_content.endswith(quote):
                            parts.append(current_content[:-1])
                            found_closing_quote = True
                            j += 1
                            break

                        parts.append(current_content)
                        j += 1

                    if found_closing_quote:
                        value = "".join(parts)
                        result.append(
                            f"{assignment_match.group(1)} ={prefix}{quote}{value}{quote}"
                        )
                        i = j
                        continue

            result.append(line)
            i += 1

        return result

    lines = text.split("\n")
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.strip() == "```python":
            result.append(line)
            i += 1

            code_lines = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1

            result.extend(process_python_lines(code_lines))

            if i < len(lines):
                result.append(lines[i])
        else:
            result.append(line)

        i += 1

    return "\n".join(result)


def format_doctest_blocks(text):

    def remove_prompt(line, prompt):
        content = line[len(prompt) :]
        if content.startswith(" "):
            content = content[1:]
        return content

    def is_output_block_start(line):
        stripped = line.strip()
        return bool(stripped) and line.startswith(" ") and stripped[0] in "[{("

    def is_output_block_line(line):
        stripped = line.strip()
        if not stripped:
            return False

        if stripped.startswith(("```", "<a ", "#", "**", "- ")):
            return False

        return line.startswith(" ")

    lines = text.split("\n")
    result = []
    i = 0
    in_code_block = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            result.append(line)
            i += 1
            continue

        if not in_code_block and stripped.startswith(">>>"):
            result.append("```python")

            while i < len(lines):
                current = lines[i]
                current_stripped = current.strip()

                if current_stripped.startswith(">>>"):
                    result.append(remove_prompt(current_stripped, ">>>"))
                    i += 1
                    continue

                if current_stripped.startswith("..."):
                    result.append(remove_prompt(current_stripped, "..."))
                    i += 1
                    continue

                break

            result.append("```")

            if i < len(lines) and is_output_block_start(lines[i]):
                result.append("```")

                while i < len(lines) and is_output_block_line(lines[i]):
                    result.append(lines[i])
                    i += 1

                result.append("```")

            continue

        result.append(line)
        i += 1

    return "\n".join(result)


def normalize_example_labels(text):
    """
    Normalize free-form example labels emitted from docstrings.

    Labels like "Example response:" are not always recognized by pydoc-markdown
    as section titles, so they can keep docstring indentation and render as
    plain text.

    Args:
        text: Markdown text content

    Returns:
        str: Text with example labels formatted as bold Markdown labels
    """
    import re

    lines = text.split("\n")
    result = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            result.append(line)
            continue

        if in_code_block:
            result.append(line)
            continue

        example_match = re.match(r"^(Example(?:\s+\w+)*):$", stripped)
        if example_match:
            result.append(f"**{example_match.group(1)}**:")
        else:
            result.append(line)

    return "\n".join(result)


def join_wrapped_list_items(text):
    """
    Join pydoc-wrapped list item descriptions into single Markdown lines.

    Source docstrings can keep short lines for linting, while generated docs read
    better when argument descriptions are not wrapped across multiple lines.

    Args:
        text: Markdown text content

    Returns:
        str: Text with wrapped list item descriptions joined
    """
    lines = text.split("\n")
    result = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            result.append(line)
            continue

        if in_code_block:
            result.append(line)
            continue

        is_list_continuation = (
            result
            and result[-1].startswith("- ")
            and line.startswith(" ")
            and bool(stripped)
            and not stripped.startswith(("- ", "* ", "```", "<a ", "#", "**"))
        )

        if is_list_continuation:
            result[-1] = f"{result[-1].rstrip()} {stripped}"
        else:
            result.append(line)

    return "\n".join(result)


def unescape_markdown_underscores(text):
    """
    Remove pydoc-markdown underscore escaping outside code blocks.

    Markdown/MDX can render underscores inside identifiers without backslashes,
    and keeping them escaped makes API names harder to read.

    Args:
        text: Markdown text content

    Returns:
        str: Text with readable Python identifiers in headings and descriptions
    """
    lines = text.split("\n")
    result = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            result.append(line)
        elif in_code_block:
            result.append(line)
        else:
            result.append(line.replace("\\_", "_"))

    return "\n".join(result)


def escape_mdx_syntax(text):
    """
    Escape MDX special characters that cause parsing issues.

    Only escapes curly braces OUTSIDE of code blocks and inline code.

    Args:
        text: Markdown text content

    Returns:
        str: Text with MDX-safe escaping
    """
    import re

    # Use line-by-line processing to handle indented code blocks
    lines = text.split("\n")
    result = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        # Check for code block markers (handles indented blocks)
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            result.append(line)
        elif in_code_block:
            # Inside code block - don't escape anything
            result.append(line)
        else:
            # Outside code block - escape curly braces but preserve inline code
            inline_code_pattern = r"(`[^`]+`)"
            segments = re.split(inline_code_pattern, line)

            escaped_segments = []
            for segment in segments:
                if segment.startswith("`") and segment.endswith("`"):
                    # Inline code - don't escape
                    escaped_segments.append(segment)
                else:
                    # Regular text - escape curly braces without adding visible slashes
                    escaped_segments.append(
                        segment.replace("{", "&#123;").replace("}", "&#125;")
                    )

            result.append("".join(escaped_segments))

    return "\n".join(result)


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


def postprocess_markdown(output):
    """Run every Markdown post-processing pass in the canonical order."""
    # Format function signatures
    output = format_function_signatures(output)

    # Remove extra indentation from code blocks
    output = dedent_code_blocks(output)

    # Join code-block assignments split across string literal lines
    output = join_split_string_assignments(output)

    # Convert doctest examples to regular Python code blocks
    output = format_doctest_blocks(output)

    # Format free-form example labels as Markdown labels
    output = normalize_example_labels(output)

    # Join wrapped argument/return descriptions into single list lines
    output = join_wrapped_list_items(output)

    # Keep Python identifiers readable in headings and regular text
    output = unescape_markdown_underscores(output)

    # Escape MDX syntax
    output = escape_mdx_syntax(output)

    return output


def render_module_markdown(import_root, module_name):
    """Render one module's reference page.

    Args:
        import_root: Directory pydoc-markdown should treat as the import root.
        module_name: Dotted module path importable from import_root.

    Returns:
        str | None: Post-processed Markdown, or None when the module has no
        documentable content.
    """
    session = PydocMarkdown()

    loader = PythonLoader(search_path=[str(import_root)], modules=[module_name])
    session.loaders = [loader]

    session.processors = [
        FilterProcessor(
            expression="not name.startswith('_') and default()",
            skip_empty_modules=True,
        ),
        SmartProcessor(),
        CrossrefProcessor(),
    ]

    session.renderer = MarkdownRenderer()

    modules_data = session.load_modules()
    if not modules_data:
        return None

    # Filter out unwanted items
    for module in modules_data:
        module.members = [m for m in module.members if should_include_item(m)]

    session.process(modules_data)
    output = session.renderer.render_to_string(modules_data)

    return postprocess_markdown(output)


def get_import_root(source_dir):
    """Return the sys.path root needed to import modules under source_dir."""
    source_dir = source_dir.resolve()
    import_root = source_dir

    while (import_root / "__init__.py").exists():
        import_root = import_root.parent

    return import_root


def get_module_name(file_path, import_root):
    """Convert a Python file path to an importable module path."""
    relative_path = file_path.resolve().relative_to(import_root.resolve())
    return ".".join(relative_path.with_suffix("").parts)


def should_skip_file(file_path, source_dir):
    """Return True when a Python file should not generate public docs."""
    relative_parts = file_path.relative_to(source_dir).parts
    parent_dirs = relative_parts[:-1]

    if any(part.startswith(".") for part in parent_dirs):
        return True

    if any(part in {"tests", "utils", "__pycache__"} for part in parent_dirs):
        return True

    if file_path.name == "__init__.py":
        return True

    if file_path.name.startswith("_") and file_path.name != "_client.py":
        return True

    return False


def discover_modules(source_dir):
    """Discover Python modules under source_dir and preserve their output paths."""
    source_dir = source_dir.resolve()
    import_root = get_import_root(source_dir)
    modules = []

    for file_path in sorted(source_dir.rglob("*.py")):
        if should_skip_file(file_path, source_dir):
            continue

        module_name = get_module_name(file_path, import_root)
        output_path = file_path.relative_to(source_dir).with_suffix(".md")
        modules.append((module_name, output_path))

    return import_root, modules


def generate_docs(source_dir, output_dir):
    """Generate documentation for every discovered module in a source folder."""
    source_dir = Path(source_dir).resolve()
    output_dir = Path(output_dir).resolve()

    print("=" * 60)
    print("API Documentation Generator")
    print("=" * 60)
    print()

    if not source_dir.exists() or not source_dir.is_dir():
        print(f"✗ Source directory does not exist: {source_dir}")
        sys.exit(1)

    import_root, modules = discover_modules(source_dir)
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

    if not modules:
        print(f"No Python modules found in {source_dir}")
        return

    print(f"✓ Source directory: {source_dir}")
    print(f"✓ Import root: {import_root}")

    # Output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"✓ Output directory: {output_dir}")
    print()

    for module_name, relative_output_path in modules:
        print(f"→ Processing {module_name}...")

        try:
            output = render_module_markdown(import_root, module_name)
            if output is None:
                print(f"No data found for {module_name}")
                continue

            # Write to file
            output_file = output_dir / relative_output_path
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(output)
            print(f"Generated {output_file.relative_to(output_dir)}")

        except Exception as e:
            print(f"Error: {e}")
            continue

    print()
    print("=" * 60)

    # List generated files
    md_files = list(output_dir.rglob("*.md"))
    if md_files:
        print(f"Generated {len(md_files)} documentation file(s):")
        for file in sorted(md_files):
            print(f"  - {file.relative_to(output_dir)}")
    else:
        print("No documentation files were generated")

    print("=" * 60)


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Generate API documentation for Python modules in a source folder."
    )
    parser.add_argument(
        "source_dir",
        type=Path,
        help="Source folder to scan recursively.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        required=True,
        help="Output folder for generated markdown files.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    generate_docs(args.source_dir, args.output_dir)
