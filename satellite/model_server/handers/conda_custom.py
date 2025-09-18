import hashlib
import json
import os
import shlex
from fnnx.envs._common import run_cmd
from fnnx.envs._common import select_pip_deps
from fnnx.console import console
from fnnx.utils import get_python_version
from fnnx.envs._common import which
import shutil
import platform
import subprocess
import tempfile


class CondaLikeEnvManager:
    def __init__(self, env_spec: dict, accelerator: str | None = None):
        self._exe = self._get_exe()
        self.env_spec = env_spec
        self.accelerator = (accelerator or "cpu").lower()
        self.channels = env_spec.get("conda_channels") or ["conda-forge"]

        self.python_version = env_spec.get("python_version") or get_python_version(micro=False)
        self.build_deps = env_spec.get("build_dependencies") or []
        deps = env_spec.get("dependencies") or []

        if not deps:
            deps.append({"package": "fnnx[core]"})

        self.selected_pip_deps = select_pip_deps(deps, self.accelerator)

        self.env_id = self._calculate_env_id()

        self._env_path: str | None = None

    def _get_exe(self) -> str:
        env_path = os.environ.get("FNNX_CONDA_EXE")

        which_hits = [which(x) for x in ("micromamba", "mamba", "conda")]

        prefixes = [
            "/opt/conda",
            "/usr/local/conda",
            "/usr/local/miniconda3",
            "/usr/local/mambaforge",
            "/usr/local/miniforge3",
            "/usr/local/anaconda3",
            "/miniconda3",
            "/mambaforge",
            "/miniforge3",
            "/anaconda3",
            os.path.expanduser("~/miniconda3"),
            os.path.expanduser("~/miniconda"),
            os.path.expanduser("~/anaconda3"),
            os.path.expanduser("~/anaconda"),
            os.path.expanduser("~/miniforge3"),
            os.path.expanduser("~/mambaforge"),
            os.path.expanduser("~/micromamba"),
            "/content",  # for Google Colab
            os.getcwd(),
        ]

        paths = []

        for p in prefixes:
            paths.extend(
                [
                    os.path.join(p, "bin", "micromamba"),
                    os.path.join(p, "bin", "mamba"),
                    os.path.join(p, "bin", "conda"),
                    os.path.join(p, "condabin", "conda"),
                    os.path.join(p, "condabin", "mamba"),
                ]
            )

        system_bins = ["/usr/bin", "/usr/local/bin", "/bin", "/sbin", "/usr/sbin"]
        for b in system_bins:
            paths.extend([os.path.join(b, n) for n in ("micromamba", "mamba", "conda")])

        candidates = [env_path, *which_hits, *paths]
        candidates = [c for c in candidates if c is not None]

        exe = next(
            (c for c in candidates if c and os.path.exists(c) and os.access(c, os.X_OK)),
            None,
        )
        if exe is None:
            raise RuntimeError(
                "Could not find conda/mamba/microconda executable. "
                "Please install conda or set FNNX_CONDA_EXE environment variable."
            )
        console.info(f"Found conda-like executable: {exe}")
        return exe

    def _calculate_env_id(self) -> str:
        spec = {
            "python_version": self.python_version,
            "build_dependencies": self.build_deps,
            "dependencies": self.selected_pip_deps,
            "conda_channels": self.channels,
        }

        spec_json = json.dumps(spec, sort_keys=True).encode()
        return hashlib.sha256(spec_json).hexdigest()

    def _create_env(
        self,
        env_name: str,
        python_version: str,
        build_deps: list[str],
        deps: list[dict],
    ):
        cmd = [
            self._exe,
            "create",
            "-n",
            env_name,
            "-y",
            f"python={python_version}",
        ]
        cmd += build_deps
        for ch in self.channels:
            cmd += ["-c", ch]
        cmd += ["--override-channels"]
        console.rule("Environment Setup")
        console.cmd(cmd, label="conda")
        with console.spinner(f"Creating environment {env_name}", detail=shlex.join(cmd)):
            run_cmd(cmd)

        req_lines: list[str] = []
        has_hash = False
        for dep in deps:
            pkg = dep["package"]  # e.g. 'pkg ; sys_platform == win32'
            extra = (
                dep.get("extra_pip_args") or ""
            )  # e.g. '--extra-index-url https://... --hash=sha256:...'
            line = f"{pkg} {extra}".strip()
            req_lines.append(line)
            if "--hash=" in line:
                has_hash = True

        req_file = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", suffix=".txt", delete=False
            ) as tf:
                tf.write("\n".join(req_lines) + "\n")
                req_file = tf.name

            pip_cmd = [
                self._exe,
                "run",
                "-n",
                env_name,
                "python",
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
            ]
            if has_hash:
                pip_cmd.append("--require-hashes")
            pip_cmd += ["-r", req_file]

            console.cmd(pip_cmd, label="pip")
            with console.spinner(
                f"Installing {len(req_lines)} pip package(s)",
                detail=shlex.join(pip_cmd),
            ):
                run_cmd(pip_cmd)
        finally:
            if req_file:
                try:
                    os.unlink(req_file)
                except OSError:
                    pass

    def python_cmd(self, argv: list[str]) -> list[str]:
        if self._env_path is None:
            raise RuntimeError("Environment not ensured; call ensure() first")
        live = (
            ["--live-stream", "--no-capture-output"]
            if self._exe.endswith("conda")
            else ["-a", '""']
        )
        return [
            self._exe,
            "run",
            "-p",
            self._env_path,
            *live,
            "python",
            "-u",
            *argv,
        ]

    def _env_exists(self, env_name: str) -> str | None:
        try:
            out = run_cmd([self._exe, "env", "list", "--json"])
            data = json.loads(out)
            if isinstance(data, dict):
                if "envs" in data and isinstance(data["envs"], list):
                    for p in data["envs"]:
                        if isinstance(p, str) and os.path.basename(p) == env_name:
                            return p
                if "name" in data and data.get("name") == env_name and "prefix" in data:
                    return data["prefix"]
            return None
        except Exception:
            return None

    def ensure(self):
        env_name = f"fnnx-{self.env_id}"
        console.info(f"Using conda-like environment: {env_name}")
        env_path = self._env_exists(env_name)
        if not env_path:
            console.warn("Environment not found; creating...")
            self._create_env(
                env_name,
                self.python_version,
                self.build_deps,
                self.selected_pip_deps,
            )
            env_path = self._env_exists(env_name)

            if not env_path:
                import glob

                env_dirs = glob.glob(f"/root/.local/share/mamba/envs/{env_name}")
                if env_dirs:
                    env_path = env_dirs[0]
                    console.warn(f"Found environment via glob: {env_path}")
        else:
            console.success("Environment already exists, reusing...")

        self._env_path = env_path
        return self._env_path


def install_micromamba(target_path: str = "bin/micromamba") -> None:
    if shutil.which("micromamba"):
        console.info("Micromamba is already installed.")
        return

    system = platform.system().lower()
    machine = platform.machine().lower()

    urls = {
        ("linux", "x86_64"): "https://micro.mamba.pm/api/micromamba/linux-64/latest",
        (
            "linux",
            "aarch64",
        ): "https://micro.mamba.pm/api/micromamba/linux-aarch64/latest",
        (
            "linux",
            "ppc64le",
        ): "https://micro.mamba.pm/api/micromamba/linux-ppc64le/latest",
        ("darwin", "x86_64"): "https://micro.mamba.pm/api/micromamba/osx-64/latest",
        ("darwin", "arm64"): "https://micro.mamba.pm/api/micromamba/osx-arm64/latest",
    }

    key = (system, machine)
    if key not in urls:
        console.error(f"Unsupported system/architecture: {system} {machine}")
        raise RuntimeError(f"Unsupported system/architecture: {system} {machine}")

    url = urls[key]
    cmd = ["sh", "-c", f"curl -Ls {url} | tar -xvj {target_path}"]

    console.cmd(cmd)
    with console.spinner("Installing micromamba", f"{system} {machine} → {target_path}"):
        subprocess.run(cmd, check=True)
