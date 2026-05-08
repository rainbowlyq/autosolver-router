uv run run_local.py data/large_seed301.txt --eval
uv run pack.py
uv run benchmark.py
uv run leaderboard.py
uv run eval.py 340e49b799b7494485ea573ae75fffe0
uv run eval.py d4489e42b3234d199798f2215d28cd1e
uv run eval.py 396130eb93d345ebb7a2db7370c2216a