#!/usr/bin/env python3
"""One-file reproduction of a LUML API behaviour. Copy, edit the REPRO section, run.

    python repro_bug_1234.py                       # against the dev stack
    python repro_bug_1234.py --base-url https://api.luml.ai
    python repro_bug_1234.py --keep                # leave created resources behind

Every HTTP request is logged to the console and to `<script name>.jsonl`, so the
run can be attached to a bug report as it is. Resources created by the run are
deleted afterwards unless `--keep` is given.

Reads LUML_API_KEY from the environment. Never put a key in this file - it is
meant to be pasted into issues.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _ensure_sdk_on_path() -> None:
    """Work against an installed luml_api, or the checkout this script sits in."""
    try:
        import luml_api  # noqa: F401
    except ImportError:
        for parent in Path(__file__).resolve().parents:
            candidate = parent / "sdk" / "python" / "api"
            if candidate.is_dir():
                sys.path.insert(0, str(candidate))
                sys.path.insert(0, str(parent / "sdk" / "python" / "sdk"))
                return


_ensure_sdk_on_path()

import luml_trace  # noqa: E402
from luml_api import LumlClient  # noqa: E402

DEV_STACK = "http://localhost:8000"

# A unique tag on everything this run creates, so leftovers are easy to spot.
RUN_ID = uuid.uuid4().hex[:8]
_cleanup: list = []


def step(message: str) -> None:
    print(f"\n=== {message}", file=sys.stderr)


def on_cleanup(fn) -> None:
    """Register a call to undo something this run created."""
    _cleanup.append(fn)


def repro(luml: LumlClient) -> None:
    step("1. what the setup is")
    collection = luml.collections.get()
    print(f"collection: {collection}", file=sys.stderr)

    step("2. the call that misbehaves")
    artifacts = luml.artifacts.list(limit=5)
    print(f"artifacts: {artifacts}", file=sys.stderr)

    step("3. what was expected vs what happened")
    # assert ..., "expected X, got Y"

    # Anything created here should register its undo, for example:
    #   created = luml.collections.create(
    #       name=f"repro-{RUN_ID}", description="repro", type=CollectionType.MODEL
    #   )
    #   on_cleanup(lambda: luml.collections.delete(str(created.id)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("LUML_BASE_URL", DEV_STACK))
    parser.add_argument("--organization", default=os.environ.get("LUML_ORGANIZATION"))
    parser.add_argument("--orbit", default=os.environ.get("LUML_ORBIT"))
    parser.add_argument("--collection", default=os.environ.get("LUML_COLLECTION"))
    parser.add_argument("--keep", action="store_true", help="skip cleanup")
    parser.add_argument("--log", default=f"{Path(__file__).stem}.jsonl")
    args = parser.parse_args()

    api_key = os.environ.get("LUML_API_KEY")
    if not api_key:
        print("LUML_API_KEY is not set", file=sys.stderr)
        return 2

    print(f"run {RUN_ID} against {args.base_url}, log -> {args.log}", file=sys.stderr)

    failed = False
    with luml_trace.trace(args.log):
        luml = LumlClient(
            base_url=args.base_url,
            api_key=api_key,
            organization=args.organization,
            orbit=args.orbit,
            collection=args.collection,
        )
        try:
            repro(luml)
        except Exception:  # noqa: BLE001 - a repro catches whatever the bug raises,
            failed = True  # including response-parsing errors, so cleanup still runs
            traceback.print_exc()
        finally:
            if args.keep:
                print(f"\n--keep: {len(_cleanup)} resource(s) left behind, "
                      f"tagged {RUN_ID}", file=sys.stderr)
            else:
                for undo in reversed(_cleanup):
                    try:
                        undo()
                    except Exception as exc:  # noqa: BLE001
                        print(f"cleanup failed: {exc!r}", file=sys.stderr)

    print(f"\n{'REPRODUCED' if failed else 'completed without the failure'}; "
          f"requests in {args.log}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
