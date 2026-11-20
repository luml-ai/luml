import sys

from luml_mlflow._skills import run_module

if __name__ == "__main__":
    raise SystemExit(run_module("luml_mlflow", sys.argv[1:]))
