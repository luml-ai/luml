import os
import shutil
import subprocess
from pathlib import Path
from typing import NoReturn

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

SKIP_ENV_VAR = "LUMLFLOW_BUILD_NO_FRONTEND"

# lumlflow-ui compiles against the type declarations the other two workspace
# packages emit, so their builds have to land first.
WORKSPACE_BUILD_ORDER = ("@luml/experiments", "@luml/attachments", "lumlflow-ui")

# Kept ASCII: this text reaches consoles of unknown encoding during pip installs.
REMEDIES = (
    "Remedies:\n"
    "  * build from the luml monorepo, whose npm workspace root (the "
    "package-lock.json next to lumlflow/) lets this hook compile the web app; or\n"
    "  * install from an artifact that already carries the bundle - the published "
    "sdist and wheel both ship lumlflow/static/; or\n"
    f"  * set {SKIP_ENV_VAR}=1 to deliberately build without the web UI."
)


class FrontendBuildHook(BuildHookInterface):
    """Puts the compiled web app in `lumlflow/static/` before a target is built.

    Inclusion is *not* this hook's job: `tool.hatch.build.artifacts` in
    pyproject.toml is what carries `lumlflow/static/` past the gitignore into
    every target. The hook only guarantees the directory is there — or fails
    loudly saying why it cannot be.
    """

    PLUGIN_NAME = "frontend"

    def initialize(self, version: str, build_data: dict) -> None:
        root = Path(self.root)
        frontend_dir = root / "frontend"
        static_dir = root / "lumlflow" / "static"
        workspace_dir = (root / "..").resolve()

        if os.environ.get(SKIP_ENV_VAR) == "1":
            self._announce(
                f"WARNING: {SKIP_ENV_VAR}=1 - building lumlflow without the web "
                "UI. The resulting artifact serves the API only; `lumlflow ui` "
                "will have no single-page app to serve."
            )
            return

        has_bundle = (static_dir / "index.html").is_file()

        if not frontend_dir.is_dir():
            # The shape a source install has: the sdist ships the bundle and no
            # frontend sources, so there is nothing to build and nothing to say.
            if has_bundle:
                return
            self._fail(
                "Cannot build lumlflow: there are no frontend sources "
                f"({frontend_dir}) and no prebuilt web app "
                f"({static_dir / 'index.html'})."
            )

        if not (workspace_dir / "package-lock.json").is_file():
            if has_bundle:
                self._announce(
                    f"NOTICE: no npm workspace root at {workspace_dir}, so the "
                    "frontend sources cannot be compiled; falling back to the "
                    f"prebuilt web app in {static_dir}."
                )
                return
            self._fail(
                f"Cannot build lumlflow's web app: {frontend_dir} is present but "
                f"the npm workspace root ({workspace_dir / 'package-lock.json'}) "
                "is missing, and there is no prebuilt web app to fall back on."
            )

        self._npm_build(workspace_dir)
        self._install_bundle(frontend_dir / "dist", static_dir)

    def _npm_build(self, workspace_dir: Path) -> None:
        subprocess.run(["npm", "ci"], cwd=workspace_dir, check=True)
        for package in WORKSPACE_BUILD_ORDER:
            subprocess.run(
                ["npm", "run", "build", f"--workspace={package}"],
                cwd=workspace_dir,
                check=True,
            )

    def _install_bundle(self, dist_dir: Path, static_dir: Path) -> None:
        if not (dist_dir / "index.html").is_file():
            self._fail(
                "The npm workspace build reported success but produced no "
                f"{dist_dir / 'index.html'}."
            )

        if static_dir.exists():
            shutil.rmtree(static_dir)
        shutil.copytree(dist_dir, static_dir)

    def _announce(self, message: str) -> None:
        print(message, flush=True)

    def _fail(self, problem: str) -> NoReturn:
        raise RuntimeError(f"{problem}\n\n{REMEDIES}")
