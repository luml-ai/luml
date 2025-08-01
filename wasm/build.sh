cd ./packages/dfs_webworker
python -m build 
cp dist/*.whl ../../../frontend/public/

cd ..


python flatten.py ./packages/promptopt/promptopt/graph.py tmp_merged.py ./packages/promptopt
mv tmp_merged.py ./packages/dfs_webworker/dfs_webworker/prompt_optimization/serialization/__fnnx_autogen_content.py
python inject_pyfunc.py

cd promptopt

python -m build

cp dist/*.whl ../../../frontend/public/

cd ../..
