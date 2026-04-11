import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class FrontendBuildHook(BuildHookInterface):
    PLUGIN_NAME = "frontend"

    def initialize(self, version: str, build_data: dict) -> None:
        package_root = Path(self.root)
        repo_root = package_root.parent
        frontend_dir = package_root / "frontend"
        static_dir = package_root / "lumlflow" / "static"
        force_include = build_data.setdefault("force_include", {})

        workspace_manifest = repo_root / "package.json"
        workspace_lockfile = repo_root / "package-lock.json"
        if workspace_manifest.exists() and workspace_lockfile.exists():
            if not frontend_dir.exists():
                raise RuntimeError(
                    "lumlflow frontend workspace is missing at "
                    f"{frontend_dir}. The Python package build requires the "
                    "repository workspace checkout to include lumlflow/frontend."
                )
            subprocess.run(
                ["npm", "ci"],
                cwd=repo_root,
                check=True,
            )
            for dep in ("@luml/experiments", "@luml/attachments"):
                subprocess.run(
                    ["npm", "run", "build", f"--workspace={dep}"],
                    cwd=repo_root,
                    check=True,
                )
            subprocess.run(
                ["npm", "run", "build", "--workspace=lumlflow-ui"],
                cwd=repo_root,
                check=True,
            )
        elif static_dir.exists():
            force_include[str(static_dir)] = "lumlflow/static"
            return
        else:
            raise RuntimeError(
                "lumlflow frontend must be built from the repository root workspace "
                "or from a source artifact that already contains lumlflow/static."
            )

        # Copy dist to static
        dist_dir = frontend_dir / "dist"
        if dist_dir.exists():
            import shutil

            if static_dir.exists():
                shutil.rmtree(static_dir)
            shutil.copytree(dist_dir, static_dir)

            # Include static directory in wheel
            force_include[str(static_dir)] = "lumlflow/static"
