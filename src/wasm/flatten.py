import sys
import os
import ast
import importlib.util
from collections import OrderedDict
import re


class ModuleFlattener:
    def __init__(self, base_dir=None):
        self.processed_modules = OrderedDict()
        self.module_contents = OrderedDict()
        self.current_path = os.getcwd()
        self.base_dir = os.path.abspath(base_dir or self.current_path)
        self.import_stack = []
        self.max_depth = 500
        self.standard_imports = {}  # Import x, import x.y, import x as y
        self.from_imports = {}  # from x import y, from x.y import z

    def is_project_module(self, module_path):
        if not module_path:
            return False

        abs_path = os.path.abspath(module_path)
        return abs_path.startswith(self.base_dir)

    def get_module_path(self, module_name, current_file=None):
        try:
            if module_name.startswith("."):
                if current_file:
                    parent_dir = os.path.dirname(os.path.abspath(current_file))
                    level = 0
                    while module_name.startswith("."):
                        level += 1
                        module_name = module_name[1:]

                    for _ in range(level - 1):
                        parent_dir = os.path.dirname(parent_dir)

                    if module_name:
                        module_path = os.path.join(parent_dir, *module_name.split("."))
                    else:
                        module_path = parent_dir

                    if os.path.isdir(module_path):
                        init_path = os.path.join(module_path, "__init__.py")
                        if os.path.exists(init_path):
                            return init_path
                    py_path = f"{module_path}.py"
                    if os.path.exists(py_path):
                        return py_path
            else:
                parts = module_name.split(".")
                for i in range(len(parts), 0, -1):
                    prefix = ".".join(parts[:i])
                    remainder = parts[i:]

                    module_path = os.path.join(self.base_dir, *prefix.split("."))
                    if os.path.isdir(module_path):
                        if remainder:
                            module_path = os.path.join(module_path, *remainder)
                        if os.path.isdir(module_path):
                            init_path = os.path.join(module_path, "__init__.py")
                            if os.path.exists(init_path):
                                return init_path
                        py_path = f"{module_path}.py"
                        if os.path.exists(py_path):
                            return py_path

                spec = importlib.util.find_spec(module_name)
                if spec and spec.origin and not spec.origin.startswith("<"):
                    return spec.origin
        except (ImportError, ValueError, AttributeError):
            pass

        return None

    def collect_imports(self, content, file_path):
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                # Standard imports: import x, import x.y, import x as y
                if isinstance(node, ast.Import):
                    for name in node.names:
                        module_path = self.get_module_path(name.name, file_path)

                        # Only preserve external imports
                        if not module_path or not self.is_project_module(module_path):
                            if name.name not in self.standard_imports:
                                self.standard_imports[name.name] = name.asname

                # From imports: from x import y, from x.y import z
                elif isinstance(node, ast.ImportFrom):
                    if node.level == 0:  # Not a relative import
                        module_path = self.get_module_path(node.module, file_path)

                        # Only preserve external imports
                        if not module_path or not self.is_project_module(module_path):
                            module_name = node.module

                            if module_name not in self.from_imports:
                                self.from_imports[module_name] = {}

                            for name in node.names:
                                self.from_imports[module_name][name.name] = name.asname
        except Exception as e:
            pass

    def process_imports(self, file_path, content, depth=0):
        if depth > self.max_depth:
            return

        try:
            tree = ast.parse(content)
            imports = []

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        imports.append((name.name, False))
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    if node.module:
                        imports.append((node.module, True))
                elif isinstance(node, ast.ImportFrom) and node.level > 0:
                    rel_module = "." * node.level
                    if node.module:
                        rel_module += node.module
                    imports.append((rel_module, True))

            for module_name, is_from in imports:
                if module_name.split(".")[
                    0
                ] in sys.builtin_module_names or module_name.startswith("__"):
                    continue

                module_path = self.get_module_path(module_name, file_path)

                # Skip external modules but keep processing internal ones
                if (
                    not module_path
                    or not os.path.exists(module_path)
                    or not self.is_project_module(module_path)
                ):
                    continue

                if module_path not in self.processed_modules:
                    self.process_file(module_path, depth + 1)

        except Exception as e:
            pass

    def process_file(self, file_path, depth=0):
        abs_path = os.path.abspath(file_path)

        if abs_path in self.processed_modules:
            return

        if abs_path in self.import_stack:
            return

        self.import_stack.append(abs_path)

        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Collect all imports from this file
            self.collect_imports(content, abs_path)

            # Process imports first
            self.process_imports(abs_path, content, depth)

            # Mark as processed
            self.processed_modules[abs_path] = True

            # Modify content to avoid executing __main__ blocks
            content = re.sub(
                r'if\s+__name__\s*==\s*([\'"])__main__\1\s*:', "if False:", content
            )

            # Process the content to remove import statements (we'll add them back at the top)
            try:
                tree = ast.parse(content)
                import_lines = []

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                        end_lineno = (
                            node.end_lineno
                            if hasattr(node, "end_lineno")
                            else node.lineno
                        )
                        import_lines.append((node.lineno, end_lineno))

                # Sort in reverse order to avoid line number issues when replacing
                import_lines.sort(reverse=True)

                # Convert content to lines for easier manipulation
                content_lines = content.splitlines()

                for start_line, end_line in import_lines:
                    # Convert to 0-based indexing
                    start_idx = start_line - 1
                    end_idx = end_line

                    # Remove import lines
                    if 0 <= start_idx < len(content_lines) and 0 <= end_idx <= len(
                        content_lines
                    ):
                        content_lines = (
                            content_lines[:start_idx] + content_lines[end_idx:]
                        )

                # Rejoin the lines
                content = "\n".join(content_lines)

            except:
                # Fall back to regex-based import removal
                content = re.sub(r"^import\s+.*?$", "", content, flags=re.MULTILINE)
                content = re.sub(
                    r"^from\s+.*?import\s+.*?$", "", content, flags=re.MULTILINE
                )

            # Store module content
            self.module_contents[abs_path] = content

        except Exception as e:
            pass
        finally:
            if self.import_stack and self.import_stack[-1] == abs_path:
                self.import_stack.pop()

    def flatten(self, main_file, output_file):
        if not self.base_dir or self.base_dir == self.current_path:
            self.base_dir = os.path.dirname(os.path.abspath(main_file))

        self.process_file(main_file)

        if not self.module_contents:
            print("Error: No modules were processed.")
            return False

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("# This file is auto-generated. Do not edit.\n\n")
            for module_name, alias in sorted(self.standard_imports.items()):
                if alias:
                    f.write(f"import {module_name} as {alias}\n")
                else:
                    f.write(f"import {module_name}\n")

            if self.standard_imports:
                f.write("\n")

            for module_name, names in sorted(self.from_imports.items()):
                if names:
                    formatted_names = []
                    for name, alias in sorted(names.items()):
                        if alias:
                            formatted_names.append(f"{name} as {alias}")
                        else:
                            formatted_names.append(name)

                    f.write(f"from {module_name} import {', '.join(formatted_names)}\n")

            if self.from_imports:
                f.write("\n")

            for content in self.module_contents.values():
                if content.strip():
                    f.write(f"{content}\n\n")

        return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "Usage: python module_flattener.py <main_module.py> <output.py> [base_directory]"
        )
        sys.exit(1)

    main_file = sys.argv[1]
    output_file = sys.argv[2]
    base_dir = sys.argv[3] if len(sys.argv) > 3 else None

    flattener = ModuleFlattener(base_dir)
    if flattener.flatten(main_file, output_file):
        print(f"Module successfully flattened to {output_file}")
    else:
        sys.exit(1)
