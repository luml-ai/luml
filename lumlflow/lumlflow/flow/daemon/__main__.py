"""The detached daemon role spawned by the first caller."""

from lumlflow.flow.daemon.main import main

if __name__ == "__main__":
    raise SystemExit(main())
