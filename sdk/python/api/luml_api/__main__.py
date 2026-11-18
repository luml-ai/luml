import sys

from luml_api._skills import run_module

if __name__ == "__main__":
    raise SystemExit(run_module("luml_api", sys.argv[1:]))
