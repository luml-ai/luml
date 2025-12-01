#!/usr/bin/env python3
"""
Script to generate API documentation using pydoc-markdown.
"""

import sys
from pathlib import Path

# Get script directory and project root
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR
SDK_PATH = PROJECT_ROOT / "sdk" / "python"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "docs" / "sdk"

# Add the SDK to Python path
sys.path.insert(0, str(SDK_PATH))

try:
    from pydoc_markdown import PydocMarkdown
    from pydoc_markdown.contrib.loaders.python import PythonLoader
    from pydoc_markdown.contrib.renderers.markdown import MarkdownRenderer
    from pydoc_markdown.contrib.processors.filter import FilterProcessor
    from pydoc_markdown.contrib.processors.smart import SmartProcessor
    from pydoc_markdown.contrib.processors.crossref import CrossrefProcessor
except ImportError:
    print("✗ pydoc-markdown not found. Install it with:")
    print("   pip install pydoc-markdown")
    sys.exit(1)


def escape_mdx_syntax(text):
    """
    Escape MDX special characters that cause parsing issues.
    
    Args:
        text: Markdown text content
    
    Returns:
        str: Text with MDX-safe escaping
    """
    import re
    
    # Escape curly braces in code blocks (keep them as-is in code)
    # But escape them in regular text
    
    # Split by code blocks to handle them separately
    parts = []
    in_code_block = False
    lines = text.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check for code block markers
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            parts.append(line)
        elif in_code_block:
            # Inside code block - don't escape
            parts.append(line)
        else:
            # Outside code block - escape curly braces
            # But preserve inline code
            escaped_line = line
            
            # Find inline code segments
            inline_code_pattern = r'`[^`]+`'
            inline_codes = re.findall(inline_code_pattern, line)
            
            # Temporarily replace inline code with placeholders
            temp_line = line
            for idx, code in enumerate(inline_codes):
                temp_line = temp_line.replace(code, f'__INLINE_CODE_{idx}__', 1)
            
            # Escape curly braces in non-code text
            temp_line = temp_line.replace('{', '\\{').replace('}', '\\}')
            
            # Restore inline code
            for idx, code in enumerate(inline_codes):
                temp_line = temp_line.replace(f'__INLINE_CODE_{idx}__', code, 1)
            
            parts.append(temp_line)
        
        i += 1
    
    return '\n'.join(parts)


def should_include_item(item):
    """
    Filter function to determine if an item should be included in docs.
    
    Args:
        item: The documentation item (class, function, etc.)
    
    Returns:
        bool: True if item should be included, False otherwise
    """
    # Exclude items starting with underscore (private)
    if item.name.startswith('_'):
        return False
    
    # Exclude abstract base classes
    if hasattr(item, 'bases'):
        for base in item.bases:
            if 'ABC' in str(base) or 'Abstract' in item.name or item.name.endswith('Base'):
                return False
    
    # Exclude specific patterns (add more as needed)
    exclude_patterns = ['Base', 'Abstract', 'Mixin']
    if any(pattern in item.name for pattern in exclude_patterns):
        return False
    
    return True


def generate_docs():
    """Generate documentation for all modules."""
    
    print("=" * 60)
    print("API Documentation Generator")
    print("=" * 60)
    print()
    
    # Output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✓ Output directory: {OUTPUT_DIR}")
    print()
    
    # Modules to document with custom file names
    # Format: "module.path": "custom-file-name"
    modules = {
        "dataforce.api._client": "client",
        "dataforce.api.resources.bucket_secrets": "bucket-secrets",
        "dataforce.api.resources.collections": "collections",
        "dataforce.api.resources.model_artifacts": "model-artifacts",
        "dataforce.api.resources.orbits": "orbits",
        "dataforce.api.resources.organizations": "organizations",
    }
    
    for module_name, file_name in modules.items():
        print(f"→ Processing {module_name}...")
        
        try:
            # Configure pydoc-markdown
            session = PydocMarkdown()
            
            # Set up loader
            loader = PythonLoader(
                search_path=[str(SDK_PATH)],
                modules=[module_name]
            )
            session.loaders = [loader]
            
            # Set up processors with filters
            session.processors = [
                FilterProcessor(
                    expression="not name.startswith('_') and default()",
                    skip_empty_modules=True
                ),
                SmartProcessor(),
                CrossrefProcessor()
            ]
            
            # Set up renderer
            session.renderer = MarkdownRenderer()
            
            # Load and process modules
            modules_data = session.load_modules()
            
            if not modules_data:
                print(f"No data found for {module_name}")
                continue
            
            # Filter out unwanted items
            for module in modules_data:
                module.members = [m for m in module.members if should_include_item(m)]
            
            # Render documentation
            session.process(modules_data)
            output = session.renderer.render_to_string(modules_data)
            
            # Escape MDX syntax
            output = escape_mdx_syntax(output)
            
            # Write to file
            output_file = OUTPUT_DIR / f"{file_name}.md"
            output_file.write_text(output)
            print(f"Generated {output_file.name}")
            
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    print()
    print("=" * 60)
    
    # List generated files
    md_files = list(OUTPUT_DIR.glob("*.md"))
    if md_files:
        print(f"Generated {len(md_files)} documentation file(s):")
        for file in sorted(md_files):
            print(f"  - {file.name}")
    else:
        print("No documentation files were generated")
    
    print("=" * 60)


if __name__ == "__main__":
    generate_docs()