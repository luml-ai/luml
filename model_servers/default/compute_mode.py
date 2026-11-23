import ast
import json
from enum import Enum
from pathlib import Path


class ComputeMode(str, Enum):  # noqa: UP042 - artifact environments support python 3.10
    SYNC = "SYNC"
    ASYNC = "ASYNC"
    UNDECIDED = "UNDECIDED"


def classify_compute(extracted_path: str | Path) -> tuple[ComputeMode, str]:
    path = Path(extracted_path)
    try:
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or not isinstance(manifest.get("variant"), str):
            return ComputeMode.UNDECIDED, "missing variant"
        if not manifest["variant"]:
            return ComputeMode.UNDECIDED, "missing variant"
        if manifest["variant"] != "pyfunc":
            return ComputeMode.ASYNC, "non-pyfunc variant uses the runtime executor"
        config = json.loads((path / "variant_config.json").read_text(encoding="utf-8"))
        if not isinstance(config, dict) or not isinstance(config.get("pyfunc_classname"), str):
            return ComputeMode.UNDECIDED, "missing pyfunc class name"
        source = ast.parse((path / "variant_artifacts/__pyfunc__.py").read_text(encoding="utf-8"))
    except (OSError, ValueError, SyntaxError) as error:
        return ComputeMode.UNDECIDED, f"artifact source unavailable ({type(error).__name__})"

    classes = {node.name: node for node in source.body if isinstance(node, ast.ClassDef)}

    def local_mro(name: str, ancestors: set[str]) -> list[str] | None:
        if name in ancestors:
            return None
        if name not in classes:
            # retain unknown bases so method lookup stops if they take precedence
            return [name]
        cls = classes[name]
        if cls.decorator_list or cls.keywords:
            return None
        bases = []
        for base in cls.bases:
            if not isinstance(base, ast.Name):
                return None
            bases.append(base.id)
        sequences = []
        for base in bases:
            order = local_mro(base, ancestors | {name})
            if order is None:
                return None
            sequences.append(order)
        sequences.append(bases.copy())
        result = [name]
        while sequences := [sequence for sequence in sequences if sequence]:
            candidate = next(
                (
                    sequence[0]
                    for sequence in sequences
                    if all(sequence[0] not in other[1:] for other in sequences)
                ),
                None,
            )
            if candidate is None:
                return None
            result.append(candidate)
            for sequence in sequences:
                if sequence[0] == candidate:
                    sequence.pop(0)
        return result

    classname = config["pyfunc_classname"]
    visited: set[str] = set()
    while classname in classes and classname not in visited:
        visited.add(classname)
        cls = classes[classname]
        if cls.decorator_list or cls.keywords:
            return ComputeMode.UNDECIDED, "dynamic pyfunc class"
        method = next(
            (
                node
                for node in reversed(cls.body)
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                and node.name == "compute_async"
            ),
            None,
        )
        if method is not None:
            if method.decorator_list:
                return ComputeMode.UNDECIDED, "decorated compute_async method"
            body = method.body
            if (
                isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body = body[1:]
            if body and isinstance(body[0], ast.Raise):
                exception = body[0].exc
                if isinstance(exception, ast.Call):
                    exception = exception.func
                if isinstance(exception, ast.Name) and exception.id == "NotImplementedError":
                    return ComputeMode.SYNC, "compute_async starts with NotImplementedError"

            pending: list[ast.AST] = list(body)
            while pending:
                node = pending.pop()
                if isinstance(
                    node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Lambda
                ):
                    continue
                if isinstance(node, ast.Await | ast.AsyncFor | ast.AsyncWith):
                    return ComputeMode.ASYNC, "compute_async contains asynchronous operations"
                pending.extend(ast.iter_child_nodes(node))
            return ComputeMode.SYNC, "compute_async has no asynchronous operations"

        if len(cls.bases) == 1 and isinstance(cls.bases[0], ast.Name):
            classname = cls.bases[0].id
        else:
            order = local_mro(classname, set())
            if order is None:
                break
            classname = next(
                (
                    name
                    for name in order[1:]
                    if name not in classes
                    or any(
                        isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                        and node.name == "compute_async"
                        for node in classes[name].body
                    )
                ),
                "",
            )

    return ComputeMode.UNDECIDED, "compute_async inheritance could not be resolved locally"
