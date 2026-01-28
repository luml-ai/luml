import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class FrontendBuildHook(BuildHookInterface):
    PLUGIN_NAME = "frontend"

    def initialize(self, version: str, build_data: dict) -> None:
        root = Path(self.root)
        frontend_dir = root / "frontend"
        static_dir = root / "lumlflow" / "static"

        if not frontend_dir.exists():
            return

        # Install npm dependencies
        subprocess.run(
            ["npm", "ci"],
            cwd=frontend_dir,
            check=True,
        )

        # Build frontend
        subprocess.run(
            ["npm", "run", "build"],
            cwd=frontend_dir,
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
