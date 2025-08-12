import importlib


def get_version(package: str) -> str:
    module = importlib.import_module(package)
    version = getattr(module, "__version__", None)
    if not version:
        raise ValueError(f"Could not determine the version of {package}")
    return version
