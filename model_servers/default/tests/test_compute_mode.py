import ast
import json
from pathlib import Path

import pytest

from compute_mode import ComputeMode, classify_compute

SDK_INTEGRATIONS = Path(__file__).resolve().parents[3] / "sdk/python/sdk/luml/integrations"


@pytest.fixture
def artifact(tmp_path: Path) -> Path:
    (tmp_path / "manifest.json").write_text(json.dumps({"variant": "pyfunc"}))
    (tmp_path / "variant_config.json").write_text(json.dumps({"pyfunc_classname": "Model"}))
    (tmp_path / "variant_artifacts").mkdir()
    return tmp_path


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("return self.compute(inputs, dynamic_attributes)", ComputeMode.SYNC),
        ('"docstring"\nraise NotImplementedError', ComputeMode.SYNC),
        ("raise NotImplementedError('unsupported')\nawait work()", ComputeMode.SYNC),
        ("return await work()", ComputeMode.ASYNC),
        ("async for item in work():\n    pass", ComputeMode.ASYNC),
        ("async with work():\n    pass", ComputeMode.ASYNC),
        ("async def nested():\n    await work()\nreturn {}", ComputeMode.SYNC),
        ("class Nested:\n    async def method(self):\n        await work()", ComputeMode.SYNC),
    ],
)
def test_classifies_only_the_method_scope(
    artifact: Path, method: str, expected: ComputeMode
) -> None:
    source = "class Model:\n    async def compute_async(self, inputs, dynamic_attributes):\n"
    source += "\n".join(f"        {line}" for line in method.splitlines())
    (artifact / "variant_artifacts/__pyfunc__.py").write_text(source)

    mode, reason = classify_compute(artifact)

    assert mode == expected
    assert reason


def test_follows_local_base_classes(artifact: Path) -> None:
    (artifact / "variant_artifacts/__pyfunc__.py").write_text(
        "class Parent:\n    async def compute_async(self, inputs, attrs):\n"
        "        return await work()\n"
        "class Child(Parent):\n    pass\nclass Model(Child):\n    pass\n"
    )
    assert classify_compute(artifact)[0] == ComputeMode.ASYNC


@pytest.mark.parametrize("bases", ["Left, Right", "Right, Left"])
@pytest.mark.parametrize("root_base", ["", "(PyFunc)"])
def test_local_diamond_uses_python_method_resolution_order(
    artifact: Path, bases: str, root_base: str
) -> None:
    (artifact / "variant_artifacts/__pyfunc__.py").write_text(
        f"class Root{root_base}:\n"
        "    async def compute_async(self, i, a):\n        return await work()\n"
        "class Left(Root):\n    pass\n"
        "class Right(Root):\n    async def compute_async(self, i, a):\n"
        "        return self.compute(i, a)\n"
        f"class Model({bases}):\n    pass\n"
    )
    # right overrides root even when left is the first base
    assert classify_compute(artifact)[0] == ComputeMode.SYNC


def test_local_multiple_bases_use_the_first_override(artifact: Path) -> None:
    (artifact / "variant_artifacts/__pyfunc__.py").write_text(
        "class Left:\n    async def compute_async(self, i, a):\n        return await work()\n"
        "class Right:\n    async def compute_async(self, i, a):\n        return {}\n"
        "class Model(Left, Right):\n    pass\n"
    )
    assert classify_compute(artifact)[0] == ComputeMode.ASYNC


@pytest.mark.parametrize(
    "source",
    [
        "from helpers import Parent\nclass Model(Parent):\n    pass\n",
        "class Model:\n    pass\n",
        "class Other:\n    pass\n",
        "class Model(Model):\n    pass\n",
        "class Parent:\n    pass\nclass Model(Parent, External):\n    pass\n",
        "class Model(factory()):\n    pass\n",
        "class A:\n    pass\nclass B:\n    pass\nclass AB(A, B):\n    pass\n"
        "class BA(B, A):\n    pass\nclass Model(AB, BA):\n    pass\n",
        "class Model(:\n",
    ],
)
def test_unresolved_source_is_undecided(artifact: Path, source: str) -> None:
    (artifact / "variant_artifacts/__pyfunc__.py").write_text(source)
    assert classify_compute(artifact)[0] == ComputeMode.UNDECIDED


@pytest.mark.parametrize("filename", ["manifest.json", "variant_config.json"])
@pytest.mark.parametrize("contents", [None, "{", "[]", "{}"])
def test_missing_or_invalid_metadata_is_undecided(
    artifact: Path, filename: str, contents: str | None
) -> None:
    path = artifact / filename
    if contents is None:
        path.unlink()
    else:
        path.write_text(contents)
    assert classify_compute(artifact)[0] == ComputeMode.UNDECIDED


def test_missing_pyfunc_source_is_undecided(artifact: Path) -> None:
    assert classify_compute(artifact)[0] == ComputeMode.UNDECIDED


@pytest.mark.parametrize("method", ["return await work()", "return {}"])
def test_local_inherited_method_with_external_root(artifact: Path, method: str) -> None:
    (artifact / "variant_artifacts/__pyfunc__.py").write_text(
        f"class Parent(PyFunc):\n    async def compute_async(self, i, a):\n        {method}\n"
        "class Model(Parent):\n    pass\n"
    )
    expected = ComputeMode.ASYNC if "await" in method else ComputeMode.SYNC
    assert classify_compute(artifact)[0] == expected


@pytest.mark.parametrize("bases", ["Mixin, Parent", "Parent, Mixin"])
@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("return self.compute(i, a)", ComputeMode.SYNC),
        ("raise NotImplementedError", ComputeMode.SYNC),
        ("return await work()", ComputeMode.ASYNC),
    ],
)
def test_local_multiple_inheritance_with_external_root(
    artifact: Path, bases: str, method: str, expected: ComputeMode
) -> None:
    (artifact / "variant_artifacts/__pyfunc__.py").write_text(
        "from fnnx import PyFunc\n"
        "class Mixin:\n    pass\n"
        f"class Parent(PyFunc):\n    async def compute_async(self, i, a):\n        {method}\n"
        f"class Model({bases}):\n    pass\n"
    )
    assert classify_compute(artifact)[0] == expected


@pytest.mark.parametrize("earlier_base", ["External", "Mixin"])
def test_unknown_earlier_base_keeps_local_override_undecided(
    artifact: Path, earlier_base: str
) -> None:
    (artifact / "variant_artifacts/__pyfunc__.py").write_text(
        "from helpers import External, PyFunc\n"
        "class Mixin(External):\n    pass\n"
        "class Parent(PyFunc):\n    async def compute_async(self, i, a):\n"
        "        return self.compute(i, a)\n"
        f"class Model({earlier_base}, Parent):\n    pass\n"
    )
    assert classify_compute(artifact)[0] == ComputeMode.UNDECIDED


def test_non_pyfunc_is_async_without_pyfunc_files(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text(json.dumps({"variant": "onnx"}))
    assert classify_compute(tmp_path)[0] == ComputeMode.ASYNC


@pytest.mark.parametrize("integration", ["sklearn", "xgboost", "lightgbm", "catboost", "langgraph"])
def test_sdk_templates_are_async(artifact: Path, integration: str) -> None:
    relative = "_template.py" if integration == "sklearn" else "_templates/pyfunc.py"
    source = (SDK_INTEGRATIONS / integration / "packaging" / relative).read_text()
    classname = next(node.name for node in ast.parse(source).body if isinstance(node, ast.ClassDef))
    (artifact / "variant_config.json").write_text(json.dumps({"pyfunc_classname": classname}))
    (artifact / "variant_artifacts/__pyfunc__.py").write_text(source)
    assert classify_compute(artifact)[0] == ComputeMode.ASYNC
