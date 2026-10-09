set -euo pipefail

cd "$(dirname "$0")"

# Flatten promptopt into the single module that dfs_webworker embeds in serialized
# pyfunc artifacts. This has to happen before dfs_webworker is built, otherwise the
# wheel picks up whatever __fnnx_autogen_content.py a previous run left behind (or
# ships without it at all on a clean tree).
python flatten.py ./packages/promptopt/promptopt/graph.py tmp_merged.py ./packages/promptopt
mv tmp_merged.py ./packages/dfs_webworker/dfs_webworker/prompt_optimization/serialization/__fnnx_autogen_content.py
python inject_pyfunc.py

cd ./packages/dfs_webworker
python -m build
cp dist/*.whl ../../../frontend/public/

cd ../promptopt
python -m build
cp dist/*.whl ../../../frontend/public/

cd ../..
