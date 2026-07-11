def strip_comments(code):
    lines = code.split("\n")[1:]
    stripped_lines = []
    for line in lines:
        if line.startswith("# "):
            stripped_lines.append(line[2:])
        else:
            stripped_lines.append(line)
    return "\n".join(stripped_lines)


with open(
    "packages/dfs_webworker/dfs_webworker/prompt_optimization/serialization/__fnnx_pyfunc.py",
    "r",
) as f:
    code = f.read()


code = strip_comments(code)

with open(
    "packages/dfs_webworker/dfs_webworker/prompt_optimization/serialization/__fnnx_autogen_content.py",
    "a",
) as f:
    f.write(code)
