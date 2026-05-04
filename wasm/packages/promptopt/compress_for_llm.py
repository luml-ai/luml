import os
import argparse

def collect_python_files(root_dir):
    python_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        if "__pycache__" in dirpath or dirpath.startswith("."):
            continue
        for f in filenames:
            if f.endswith(".py"):
                python_files.append(os.path.join(dirpath, f))
    return sorted(python_files)

def package_to_single_file(root_dir, output_file):
    root_dir = os.path.abspath(root_dir)
    files = collect_python_files(root_dir)
    with open(output_file, "w", encoding="utf-8") as out:
        for file in files:
            rel_path = os.path.relpath(file, root_dir)
            out.write(f"\n# ==== File: {rel_path} ====\n")
            with open(file, "r", encoding="utf-8") as f:
                out.write(f.read())
                out.write("\n")
    print(f"Package compressed into {output_file} with {len(files)} files.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flatten a Python package into a single script for LLM ingestion.")
    parser.add_argument("package_dir", help="Path to the Python package directory")
    parser.add_argument("output", help="Output file path for the combined script")
    args = parser.parse_args()

    package_to_single_file(args.package_dir, args.output)
