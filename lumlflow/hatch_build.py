import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class FrontendBuildHook(BuildHookInterface):
    PLUGIN_NAME = "frontend"

    def initialize(self, version: str, build_data: dict) -> None:
        root = Path(self.root)
        workspace_dir = (root / "..").resolve()
        frontend_dir = root / "frontend"
        static_dir = root / "lumlflow" / "static"

        if not frontend_dir.exists():
            return

        if not (workspace_dir / "package-lock.json").exists():
            return

        subprocess.run(
            ["npm", "ci"],
            cwd=workspace_dir,
            check=True,
        )

        # Build dependency packages first (lumlflow-ui needs their type declarations)
        subprocess.run(
            ["npm", "run", "build", "--workspace=@luml/experiments"],
            cwd=workspace_dir,
            check=True,
        )
        subprocess.run(
            ["npm", "run", "build", "--workspace=@luml/attachments"],
            cwd=workspace_dir,
            check=True,
        )

        # Build frontend
        subprocess.run(
            ["npm", "run", "build", "--workspace=lumlflow-ui"],
            cwd=workspace_dir,
            check=True,
        )

        # Copy dist to static
        dist_dir = frontend_dir / "dist"
        if dist_dir.exists():
            import shutil

            if static_dir.exists():
                shutil.rmtree(static_dir)
            shutil.copytree(dist_dir, static_dir)

            # Include static directory in wheel
            build_data["force_include"][str(static_dir)] = "lumlflow/static"
