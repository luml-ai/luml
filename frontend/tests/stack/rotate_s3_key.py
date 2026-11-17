"""Rotates the MinIO user's secret key and the platform's S3 bucket secret with it.

Every presigned URL issued before stops working (MinIO answers 403), as after a real
key rotation, while URLs issued afterwards work. Usage: ``python rotate_s3_key.py
<new key>``, with the environment run.sh exports.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from luml_api import LumlClient


def main() -> None:
    new_key = sys.argv[1]
    data = json.loads((Path(os.environ["E2E_WORK_DIR"]) / "platform.json").read_text())
    subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            os.environ["E2E_COMPOSE_PROJECT"],
            "-f",
            os.environ["E2E_COMPOSE_FILE"],
            "run",
            "--rm",
            "--no-deps",
            "-e",
            "MC_HOST_local=http://minioadmin:minioadmin@minio:9000",
            "--entrypoint",
            "mc",
            "minio-init",
            "admin",
            "user",
            "add",
            "local",
            "e2euser",
            new_key,
        ],
        check=True,
        capture_output=True,
    )
    client = LumlClient(
        base_url=os.environ["E2E_BACKEND_URL"],
        api_key=data["api_key"],
        organization=data["organization_id"],
    )
    client.bucket_secrets.update(
        data["storages"]["s3"]["bucket_secret_id"], secret_key=new_key
    )


if __name__ == "__main__":
    main()
