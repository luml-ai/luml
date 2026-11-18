# Verify an artifact in a fresh environment

A model that runs in your environment can still fail anywhere else. Your
environment has packages the artifact did not declare, and your working
directory has modules the artifact did not bundle. Prove the artifact is
self-contained: load it in an environment built only from its declared
dependencies, from an empty directory, and run it on a few rows.

## The check

Print the script, save it, and run it with sample inputs:

```bash
python -m luml skills show luml-sdk scripts/verify_artifact.py > verify_artifact.py
python verify_artifact.py model.luml inputs.json
```

`inputs.json` maps each input name to a list of values:

```json
{"tenure_months": [3, 40], "plan": ["pro", "free"], "monthly_spend": [49.0, 0.0]}
```

For a JSON input, the value is the object itself: `{"payload": {"question": "..."}}`.

The script reads the artifact's `env.json`, makes a throwaway environment with
`uv run --isolated` that holds only those pip packages, clears `PYTHONPATH`, and
runs the model from an empty temporary directory. It prints the outputs, or the
error and `FAILED`. It needs `uv`.

Conda build dependencies are not installed by this check. If the model needs
one, the deployment installs it; mention it to the user.

## Reading a failure

| Error | Cause | Fix |
| --- | --- | --- |
| `ModuleNotFoundError` for a project module | Local code not bundled | `extra_code_modules=[...]`, `add_module(...)`, or `cloudpickle.register_pickle_by_value(module)` |
| `ModuleNotFoundError` for a package | Package not declared | `extra_dependencies=[...]` or `add_runtime_dependency(...)` |
| `You must have numpy installed to use Array dtype` | numpy not declared | `add_runtime_dependency("numpy==...")` |
| `Can't instantiate abstract class ... compute_async` | PyFunc incomplete | Implement `warmup`, `compute` and `compute_async` |
| `FileNotFoundError` for a data or prompt file | The model reads a project file | Add it with `add_file` and read it with `get_filepath` |
| Unpickling error or version warning | Versions differ from training | Pin the training versions |

Fix the packaging, save again, and rerun until it prints `OK`.

## Without the script

Do not use fnnx's `StdIOHandler` with `UvEnvManager` for this check. When its
worker process exits, for example because the model fails to load or because the
caller's fnnx differs from the one the artifact pins, `compute()` waits forever
and shows no error. The script avoids that by running fnnx's in-process
`Runtime` inside the fresh environment.
