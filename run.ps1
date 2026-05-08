uv run run_local.py data/large_seed301.txt --eval
uv run pack.py
uv run benchmark.py
uv run eval.py 340e49b799b7494485ea573ae75fffe0