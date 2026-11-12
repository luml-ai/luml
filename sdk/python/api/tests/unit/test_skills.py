import posixpath
import re
import shutil
import subprocess
import sys
import zipfile
from importlib.resources import files
from pathlib import Path

import pytest

from luml_api import _skills
from luml_api._skills import (
    SkillError,
    list_skills,
    read_skill_file,
    render_skill,
    run_cli,
    run_module,
    skill_files,
)

PACKAGE = "luml_api"
PACKAGE_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = PACKAGE_DIR.parents[2]
SKILL_MODULE_COPIES = [
    REPO_ROOT / "sdk/python/sdk/luml/_skills.py",
    REPO_ROOT / "sdk/python/api/luml_api/_skills.py",
    REPO_ROOT / "lumlflow/lumlflow/_skills.py",
    REPO_ROOT / "extras/python/luml-mlflow/luml_mlflow/_skills.py",
]
MARKDOWN_LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


@pytest.fixture
def skills_root(tmp_path: Path) -> Path:
    root = tmp_path / "skills"
    (root / "beta/references").mkdir(parents=True)
    (root / "beta/SKILL.md").write_text(
        "---\nname: beta\ndescription: Beta skill.\n---\n\n# Beta\n"
    )
    (root / "beta/references/usage.md").write_text("usage body\n")
    (root / "beta/__pycache__").mkdir()
    (root / "beta/__pycache__/x.pyc").write_bytes(b"")
    (root / "alpha").mkdir()
    (root / "alpha/SKILL.md").write_text(
        '---\nname: alpha\ndescription: "Alpha skill."\n---\n\n# Alpha\n'
    )
    (root / "not_a_skill").mkdir()
    return root


def test_list_skills_sorted_with_descriptions(skills_root: Path) -> None:
    skills = list_skills(skills_root)

    assert [(skill.name, skill.description) for skill in skills] == [
        ("alpha", "Alpha skill."),
        ("beta", "Beta skill."),
    ]


def test_list_skills_without_skills_dir(tmp_path: Path) -> None:
    assert list_skills(tmp_path / "missing") == []


def test_skill_files_skip_caches(skills_root: Path) -> None:
    assert skill_files(skills_root, "beta") == ["SKILL.md", "references/usage.md"]


def test_render_skill_lists_other_files(skills_root: Path) -> None:
    rendered = render_skill(skills_root, "beta", "python -m pkg skills")

    assert rendered.startswith("---\nname: beta")
    assert "`python -m pkg skills show beta <file>`" in rendered
    assert rendered.endswith("- references/usage.md\n")


def test_render_skill_without_other_files(skills_root: Path) -> None:
    rendered = render_skill(skills_root, "alpha", "python -m pkg skills")

    assert rendered.endswith("# Alpha\n")
    assert "Other files" not in rendered


def test_read_reference_file(skills_root: Path) -> None:
    assert read_skill_file(skills_root, "beta", "references/usage.md") == (
        "usage body\n"
    )


@pytest.mark.parametrize(
    "path",
    ["../alpha/SKILL.md", "/etc/passwd", "references//usage.md", "references\\x"],
)
def test_read_rejects_paths_outside_skill(skills_root: Path, path: str) -> None:
    with pytest.raises(SkillError, match="invalid file path"):
        read_skill_file(skills_root, "beta", path)


def test_read_unknown_file_names_available_files(skills_root: Path) -> None:
    with pytest.raises(SkillError, match="Files: SKILL.md, references/usage.md"):
        read_skill_file(skills_root, "beta", "references/missing.md")


@pytest.mark.parametrize("name", ["missing", "not_a_skill", ".."])
def test_unknown_skill_names_available_skills(skills_root: Path, name: str) -> None:
    with pytest.raises(SkillError, match="Skills: alpha, beta"):
        skill_files(skills_root, name)


@pytest.fixture
def patched_package(monkeypatch: pytest.MonkeyPatch, skills_root: Path) -> None:
    monkeypatch.setattr(_skills, "files", lambda _package: skills_root.parent)


@pytest.mark.usefixtures("patched_package")
@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["list"], "alpha: Alpha skill.\nbeta: Beta skill.\n"),
        (["files", "beta"], "SKILL.md\nreferences/usage.md\n"),
        (["show", "beta", "references/usage.md"], "usage body\n"),
    ],
)
def test_cli_prints_output(
    capsys: pytest.CaptureFixture[str], argv: list[str], expected: str
) -> None:
    assert run_cli("pkg", "pkg skills", argv) == 0
    assert capsys.readouterr().out == expected


@pytest.mark.usefixtures("patched_package")
@pytest.mark.parametrize(
    "argv", [["show", "missing"], ["show", "beta", "nope.md"], ["files", "missing"]]
)
def test_cli_errors_exit_non_zero(
    capsys: pytest.CaptureFixture[str], argv: list[str]
) -> None:
    assert run_cli("pkg", "pkg skills", argv) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("pkg skills: ")


@pytest.mark.parametrize("argv", [[], ["other"]])
def test_module_requires_skills_command(
    capsys: pytest.CaptureFixture[str], argv: list[str]
) -> None:
    assert run_module(PACKAGE, argv) == 2
    assert f"python -m {PACKAGE} skills" in capsys.readouterr().err


def test_module_entry_point_runs() -> None:
    result = subprocess.run(
        [sys.executable, "-m", PACKAGE, "skills", "list"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_skill_module_copies_are_identical() -> None:
    present = [path for path in SKILL_MODULE_COPIES if path.exists()]
    if len(present) < len(SKILL_MODULE_COPIES):
        pytest.skip("not running inside the luml monorepo")
    contents = {path.read_text() for path in present}
    assert len(contents) == 1, "edit every copy of _skills.py together"


@pytest.mark.parametrize(
    "skill", [skill.name for skill in list_skills(files(PACKAGE) / "skills")]
)
def test_packaged_skill_links_resolve(skill: str) -> None:
    root = files(PACKAGE) / "skills"
    available = set(skill_files(root, skill))
    for path in available:
        if not path.endswith(".md"):
            continue
        folder = path.rpartition("/")[0]
        for link in MARKDOWN_LINK.findall(read_skill_file(root, skill, path)):
            if "://" in link:
                continue
            target = posixpath.normpath(posixpath.join(folder, link))
            assert target in available, f"{skill}/{path} links to missing {link}"


@pytest.mark.skipif(shutil.which("uv") is None, reason="needs uv to build a wheel")
def test_wheel_ships_skill_files(tmp_path: Path) -> None:
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path), str(PACKAGE_DIR)],
        check=True,
        capture_output=True,
    )
    (wheel,) = tmp_path.glob("*.whl")
    with zipfile.ZipFile(wheel) as archive:
        shipped = set(archive.namelist())

    source_root = PACKAGE_DIR / PACKAGE / "skills"
    expected = {
        path.relative_to(PACKAGE_DIR).as_posix()
        for path in source_root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    assert f"{PACKAGE}/_skills.py" in shipped
    assert expected <= shipped
