"""Kernel tests. These import stdlib and `lumlflow_kernel` only, so the lane
that runs them under the venv floor (Python 3.10) needs no project install:

    uv run --python 3.10 --no-project --with pytest pytest tests/kernel
"""
