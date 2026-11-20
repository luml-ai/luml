import sys

from luml._skills import run_module

if __name__ == "__main__":
    raise SystemExit(run_module("luml", sys.argv[1:]))
