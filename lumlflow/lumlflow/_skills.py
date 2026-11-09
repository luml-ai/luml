"""Agent skills shipped inside the package, printed by a small CLI.

A skill is a directory `<package>/skills/<name>/` holding a `SKILL.md` and any
reference files it links to. The CLI prints file contents rather than paths, so
agents whose sandbox cannot read site-packages can still navigate a skill.

This module is copied verbatim into luml, luml_api and lumlflow. A test in each
package keeps the copies identical, so edit all three together.
"""

import argparse
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable

ENTRY_FILE = "SKILL.md"
_SKIPPED_NAMES = {"__pycache__", "__init__.py"}


class SkillError(LookupError):
    pass


@dataclass(frozen=True)
class SkillInfo:
    name: str
    description: str


def list_skills(root: Traversable) -> list[SkillInfo]:
    if not root.is_dir():
        return []
    skills = [
        SkillInfo(entry.name, _description(entry / ENTRY_FILE))
        for entry in root.iterdir()
        if entry.is_dir() and (entry / ENTRY_FILE).is_file()
    ]
    return sorted(skills, key=lambda skill: skill.name)


def skill_files(root: Traversable, name: str) -> list[str]:
    return sorted(_walk(_skill_dir(root, name), ""))


def read_skill_file(
    root: Traversable, name: str, relative_path: str = ENTRY_FILE
) -> str:
    skill_dir = _skill_dir(root, name)
    parts = relative_path.split("/")
    if "\\" in relative_path or any(part in {"", ".", ".."} for part in parts):
        raise SkillError(
            f"invalid file path '{relative_path}': use a path relative to the "
            "skill, such as references/example.md"
        )
    target = skill_dir.joinpath(*parts)
    if not target.is_file() or parts[-1] in _SKIPPED_NAMES:
        available = ", ".join(skill_files(root, name))
        raise SkillError(
            f"skill '{name}' has no file '{relative_path}'. Files: {available}"
        )
    return target.read_text(encoding="utf-8")


def render_skill(root: Traversable, name: str, command: str) -> str:
    """Print `SKILL.md` followed by the commands that open its other files."""
    text = read_skill_file(root, name).rstrip("\n")
    other_files = [path for path in skill_files(root, name) if path != ENTRY_FILE]
    if not other_files:
        return text + "\n"
    footer = [
        "",
        "---",
        "",
        f"Other files in this skill. Print one with `{command} show {name} <file>`:",
        "",
        *(f"- {path}" for path in other_files),
    ]
    return "\n".join([text, *footer]) + "\n"


def run_cli(package: str, command: str, argv: Sequence[str]) -> int:
    """Run `list`, `show` or `files` for the skills of `package`.

    `command` is how the user invokes the skills CLI, such as
    `python -m luml skills`. It is used in help and in the `show` footer.
    """
    parser = _parser(command)
    args = parser.parse_args(argv)
    root = files(package) / "skills"
    try:
        output = _execute(args, root, command)
    except SkillError as error:
        sys.stderr.write(f"{command}: {error}\n")
        return 1
    sys.stdout.write(output)
    return 0


def run_module(package: str, argv: Sequence[str]) -> int:
    """Entry point for `python -m <package>`, whose only command is `skills`."""
    command = f"python -m {package} skills"
    if not argv or argv[0] != "skills":
        sys.stderr.write(f"usage: {command} {{list,show,files}} ...\n")
        return 2
    return run_cli(package, command, argv[1:])


def _execute(args: argparse.Namespace, root: Traversable, command: str) -> str:
    if args.action == "list":
        skills = list_skills(root)
        if not skills:
            return "No skills in this package.\n"
        return "".join(f"{skill.name}: {skill.description}\n" for skill in skills)
    if args.action == "files":
        return "".join(f"{path}\n" for path in skill_files(root, args.name))
    if args.file is None:
        return render_skill(root, args.name, command)
    return read_skill_file(root, args.name, args.file)


def _parser(command: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=command,
        description="Agent skills for the installed version of this package.",
    )
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("list", help="List the skills with their descriptions.")
    show = actions.add_parser(
        "show", help="Print a skill's SKILL.md, or one of its other files."
    )
    show.add_argument("name")
    show.add_argument(
        "file", nargs="?", help="Path inside the skill, e.g. references/x.md."
    )
    files_parser = actions.add_parser("files", help="List the files of a skill.")
    files_parser.add_argument("name")
    return parser


def _skill_dir(root: Traversable, name: str) -> Traversable:
    names = [skill.name for skill in list_skills(root)]
    if name not in names:
        available = ", ".join(names) or "none"
        raise SkillError(f"unknown skill '{name}'. Skills: {available}")
    return root / name


def _walk(directory: Traversable, prefix: str) -> Iterator[str]:
    for entry in directory.iterdir():
        if entry.name in _SKIPPED_NAMES or entry.name.startswith("."):
            continue
        path = f"{prefix}{entry.name}"
        if entry.is_dir():
            yield from _walk(entry, f"{path}/")
        else:
            yield path


def _description(skill_file: Traversable) -> str:
    """Read `description:` from the front matter; skills keep it on one line."""
    lines = skill_file.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, _, value = line.partition(":")
        if key.strip() == "description":
            return value.strip().strip("\"'")
    return ""
