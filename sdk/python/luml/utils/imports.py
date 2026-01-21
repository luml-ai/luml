import gc
import importlib
import os
import sys
from typing import Any


def get_version(package: str) -> str:
    module = importlib.import_module(package)
    version = getattr(module, "__version__", None)
    if not version:
        raise ValueError(f"Could not determine the version of {package}")
    return version


def get_object_path(obj: object) -> tuple[str, str]:  # noqa: C901
    """
    Determines the module file and object path for an arbitrary python object.

    Returns:
        tuple[str, str]: (module_file, object_path) e.g., ("agent.py", "agent::agent")
    """
    object_name = None
    module = None

    for referrer in gc.get_referrers(obj):
        if not isinstance(referrer, dict):
            continue

        for mod_name, mod in sys.modules.items():
            if mod is None or not hasattr(mod, "__dict__"):
                continue
            if referrer is mod.__dict__:
                # Found the module, now find the variable name
                for name, value in referrer.items():
                    if value is obj and not name.startswith("_"):
                        # Skip if this is the current module or __main__
                        if mod_name == __name__ or mod_name == "__main__":
                            # Save as fallback but continue searching
                            if object_name is None:
                                object_name = name
                                module = mod
                        else:
                            object_name = name
                            module = mod
                            break
                if module and module.__name__ not in (__name__, "__main__"):
                    break

    if object_name is None or module is None:
        raise ValueError(
            "Could not automatically determine object variable name or module"
        )

    if module.__name__ == "__main__":
        if module.__file__ is None:
            raise ValueError("Cannot determine module file for __main__")
        module_file = os.path.basename(module.__file__)
        module_name = os.path.splitext(module_file)[0]
    else:
        module_name = module.__name__
        module_file = module_name.split(".")[-1] + ".py"

    object_path = f"{module_name}::{object_name}"

    return module_file, object_path


def extract_top_level_modules(modules: list[str]) -> list[str]:
    top_level = []
    for m in modules:
        normalized = os.path.normpath(m)
        first_component = normalized.split(os.path.sep, 1)[0]
        top_level.append(first_component)
    return list(set(top_level))


def dyn_import(spec: str) -> Any:  # noqa: ANN401
    if "::" not in spec:
        raise ValueError(
            f"Invalid import spec '{spec}'. Expected format: 'module.path::object_name'"
        )

    parts = spec.split("::", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(
            f"Invalid import spec '{spec}'. Expected format: 'module.path::object_name'"
        )

    module_path, obj_name = parts
    module = importlib.import_module(module_path)
    return getattr(module, obj_name)
