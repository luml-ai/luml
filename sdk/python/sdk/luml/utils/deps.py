import re
import site
import sys
from collections.abc import Iterable
from importlib.metadata import distributions, version
from pathlib import Path
from typing import Final, NamedTuple


class Dependency(NamedTuple):
    name: str
    version: str
    marker: str | None = None

    def to_requirement_string(self) -> str:
        req = f"{self.name}=={self.version}"
        if self.marker:
            req += f"; {self.marker}"
        return req


WIN32: Final[str] = "sys_platform == 'win32'"
DARWIN: Final[str] = "sys_platform == 'darwin'"
LINUX: Final[str] = "sys_platform == 'linux'"
NOT_DARWIN: Final[str] = "sys_platform != 'darwin'"  # Linux + Windows
NOT_WIN32: Final[str] = "sys_platform != 'win32'"  # Linux + macOS

PLATFORM_MARKERS: dict[str, str] = {
    "pywin32": WIN32,
    "pywinpty": WIN32,
    "wmi": WIN32,
    "pypiwin32": WIN32,
    "windows-curses": WIN32,
    "win32api": WIN32,
    "win32com": WIN32,
    "pythoncom": WIN32,
    "winrt": WIN32,
    "winrt-runtime": WIN32,
    "comtypes": WIN32,
    "pyreadline": WIN32,
    "pyreadline3": WIN32,
    "directml": WIN32,
    "torch-directml": WIN32,
    "onnxruntime-directml": WIN32,
    "tensorflow-directml": WIN32,
    "tensorflow-directml-plugin": WIN32,
    "pyobjc": DARWIN,
    "pyobjc-core": DARWIN,
    "pyobjc-framework-cocoa": DARWIN,
    "pyobjc-framework-quartz": DARWIN,
    "pyobjc-framework-metal": DARWIN,
    "pyobjc-framework-metalperformanceshaders": DARWIN,
    "pyobjc-framework-coreml": DARWIN,
    "pyobjc-framework-vision": DARWIN,
    "mlx": DARWIN,
    "mlx-lm": DARWIN,
    "coremltools": DARWIN,
    "tensorflow-macos": DARWIN,
    "tensorflow-metal": DARWIN,
    "appnope": DARWIN,
    "mac-alias": DARWIN,
    "dmgbuild": DARWIN,
    "py2app": DARWIN,
    "inotify": LINUX,
    "inotify-simple": LINUX,
    "pyinotify": LINUX,
    "python-prctl": LINUX,
    "evdev": LINUX,
    "pynput-linux": LINUX,
    "rocm-smi": LINUX,
    "rocm-smi-lib": LINUX,
    "pytorch-rocm": LINUX,
    "torch-rocm": LINUX,
    "tensorflow-rocm": LINUX,
    "nvidia-cuda-runtime-cu11": NOT_DARWIN,
    "nvidia-cuda-runtime-cu12": NOT_DARWIN,
    "nvidia-cuda-cupti-cu11": NOT_DARWIN,
    "nvidia-cuda-cupti-cu12": NOT_DARWIN,
    "nvidia-cuda-nvcc-cu11": NOT_DARWIN,
    "nvidia-cuda-nvcc-cu12": NOT_DARWIN,
    "nvidia-cuda-nvrtc-cu11": NOT_DARWIN,
    "nvidia-cuda-nvrtc-cu12": NOT_DARWIN,
    "nvidia-cudnn-cu11": NOT_DARWIN,
    "nvidia-cudnn-cu12": NOT_DARWIN,
    "nvidia-nccl-cu11": NOT_DARWIN,
    "nvidia-nccl-cu12": NOT_DARWIN,
    "nvidia-cublas-cu11": NOT_DARWIN,
    "nvidia-cublas-cu12": NOT_DARWIN,
    "nvidia-cusparse-cu11": NOT_DARWIN,
    "nvidia-cusparse-cu12": NOT_DARWIN,
    "nvidia-cufft-cu11": NOT_DARWIN,
    "nvidia-cufft-cu12": NOT_DARWIN,
    "nvidia-curand-cu11": NOT_DARWIN,
    "nvidia-curand-cu12": NOT_DARWIN,
    "nvidia-cusolver-cu11": NOT_DARWIN,
    "nvidia-cusolver-cu12": NOT_DARWIN,
    "nvidia-nvtx-cu11": NOT_DARWIN,
    "nvidia-nvtx-cu12": NOT_DARWIN,
    "nvidia-nvjpeg-cu11": NOT_DARWIN,
    "nvidia-nvjpeg-cu12": NOT_DARWIN,
    "nvidia-ml-py": NOT_DARWIN,
    "nvidia-ml-py3": NOT_DARWIN,
    "pynvml": NOT_DARWIN,
    "nvidia-pyindex": NOT_DARWIN,
    "nvidia-tensorrt": NOT_DARWIN,
    "tensorrt": NOT_DARWIN,
    "tensorrt-llm": NOT_DARWIN,
    "onnxruntime-gpu": NOT_DARWIN,
    "cupy": NOT_DARWIN,
    "cupy-cuda11x": NOT_DARWIN,
    "cupy-cuda12x": NOT_DARWIN,
    "pycuda": NOT_DARWIN,
    "cuda-python": NOT_DARWIN,
    "triton": NOT_DARWIN,
    "triton-nightly": NOT_DARWIN,
    "cudf": LINUX,
    "cuml": LINUX,
    "cugraph": LINUX,
    "cuspatial": LINUX,
    "cupy-cuda": LINUX,
    "dask-cudf": LINUX,
    "rmm": LINUX,
    "intel-openmp": NOT_DARWIN,
    "mkl": NOT_DARWIN,
    "mkl-devel": NOT_DARWIN,
    "mkl-include": NOT_DARWIN,
    "intel-extension-for-pytorch": NOT_DARWIN,
    "intel-extension-for-tensorflow": NOT_DARWIN,
    "openvino": NOT_DARWIN,
    "openvino-dev": NOT_DARWIN,
    "dpctl": NOT_DARWIN,
    "dpnp": NOT_DARWIN,
    "mpi4py-mpich": LINUX,
    "horovod": NOT_DARWIN,
}

_PLATFORM_PREFIXES: dict[str, str] = {
    "pyobjc-framework-": DARWIN,
    "nvidia-cuda-": NOT_DARWIN,
    "nvidia-cu": NOT_DARWIN,
    "nvidia-nv": NOT_DARWIN,
    "cupy-cuda": NOT_DARWIN,
    "rocm-": LINUX,
    "winrt-": WIN32,
}


def _generate_cuda_suffixes() -> dict[str, str]:
    suffixes = {}

    for major in range(11, 16):
        suffixes[f"-cu{major}"] = NOT_DARWIN

        for minor in range(10):
            suffixes[f"-cu{major}{minor}"] = NOT_DARWIN

    return suffixes


_PLATFORM_SUFFIXES: dict[str, str] = {
    **_generate_cuda_suffixes(),
    "-rocm": LINUX,
    "-directml": WIN32,
    "-metal": DARWIN,
    "-macos": DARWIN,
}


def _normalize_package_name(package_name: str) -> str:
    return package_name.lower().replace("_", "-")


def _get_platform_marker(package_name: str) -> str | None:
    pkg_lower = _normalize_package_name(package_name)

    if pkg_lower in PLATFORM_MARKERS:
        return PLATFORM_MARKERS[pkg_lower]

    for prefix, marker in _PLATFORM_PREFIXES.items():
        if pkg_lower.startswith(prefix):
            return marker

    for suffix, marker in _PLATFORM_SUFFIXES.items():
        if pkg_lower.endswith(suffix):
            return marker

    return None


def is_platform_specific(package_name: str) -> bool:
    return _get_platform_marker(package_name) is not None


def get_all_platform_packages() -> dict[str, str]:
    return PLATFORM_MARKERS.copy()


def find_dependencies() -> tuple[list[str], list[str]]:  # noqa: C901
    module_to_dist: dict[str, str] = {}

    for dist in distributions():
        dist_name = dist.metadata["Name"]

        try:
            top_level = dist.read_text("top_level.txt")
            if top_level:
                for module_name in top_level.strip().split("\n"):
                    module_name = module_name.strip()
                    if module_name:
                        module_to_dist[module_name] = dist_name
        except FileNotFoundError:
            pass

        if dist.files:
            for file in dist.files:
                if file.suffix == ".py":
                    parts = file.parts
                    if parts:
                        top_module = parts[0].replace(".py", "")
                        if top_module not in module_to_dist:
                            module_to_dist[top_module] = dist_name

    site_packages: set[str] = set()

    for sp in site.getsitepackages():
        site_packages.add(sp)

    if hasattr(site, "getusersitepackages"):
        user_site = site.getusersitepackages()
        if user_site:
            site_packages.add(user_site)

    if hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        for pattern in [
            Path(sys.prefix)
            / "lib"
            / f"python{sys.version_info.major}.{sys.version_info.minor}"
            / "site-packages",
            Path(sys.prefix) / "Lib" / "site-packages",  # Windows
        ]:
            if pattern.exists():
                site_packages.add(str(pattern))

    cwd = Path.cwd()
    pip_packages: dict[str, Dependency] = {}
    local_modules: set[str] = set()

    for mod_name, mod in sys.modules.items():
        if mod is None or not hasattr(mod, "__file__") or mod.__file__ is None:
            continue
        if mod_name in sys.builtin_module_names:
            continue

        mod_path = Path(mod.__file__)

        is_site_package = any(str(mod_path).startswith(sp) for sp in site_packages)

        if is_site_package:
            top_level = mod_name.split(".")[0]

            dist_name = module_to_dist.get(top_level)

            pkg_version = None
            for name in [dist_name, top_level]:
                if name is None:
                    continue
                try:
                    pkg_version = version(name)
                    dist_name = name
                    break
                except Exception:
                    pass

            if pkg_version is None or dist_name is None:
                continue

            key = dist_name.lower().replace("_", "-")

            if key not in pip_packages:
                marker = _get_platform_marker(dist_name)
                pip_packages[key] = Dependency(
                    name=dist_name,
                    version=pkg_version,
                    marker=marker,
                )
        else:
            try:
                rel_path = mod_path.relative_to(cwd)
                if (
                    rel_path.suffix == ".py"
                    and not any(part.startswith(".") for part in rel_path.parts)
                    and "site-packages" not in rel_path.parts
                ):
                    local_modules.add(str(rel_path))
            except ValueError:
                pass

    pip_requirements = sorted(
        dep.to_requirement_string() for dep in pip_packages.values()
    )

    return pip_requirements, sorted(local_modules)


def _dep_pattern(name: str) -> re.Pattern:
    return re.compile(
        rf"""
        ^\s*                               # leading space
        {re.escape(name)}                 # package name
        (?:\[[^\]]+\])?                   # optional extras: [a,b]
        (?:                               # optional version spec(s)
            \s*
            (?:==|!=|<=|>=|<|>|~=)
            \s*
            [^;,\s]+
            (?:\s*,\s*
                (?:==|!=|<=|>=|<|>|~=)
                \s*
                [^;,\s]+
            )*
        )?
        (?:\s*;.*)?                       # optional environment marker
        \s*$                              # trailing space
        """,
        re.IGNORECASE | re.VERBOSE,
    )


def has_dependency(
    dependencies: Iterable[str],
    name: str,
) -> bool:
    pattern = _dep_pattern(name)
    return any(pattern.match(dep) for dep in dependencies)
