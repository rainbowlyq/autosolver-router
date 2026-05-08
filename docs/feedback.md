## example_solver

平均惩罚分数
1,710.58
完成算例
10 / 10
high_noise_seed601
1,521.91
30/30(100%)
144ms
large_seed301
2,097.66
40/40(100%)
153ms
large_seed302
2,349.48
40/40(100%)
160ms
low_willingness_seed501
2,522.10
30/30(100%)
144ms
medium_seed201
1,408.40
30/30(100%)
144ms
medium_seed202
1,619.23
30/30(100%)
140ms
medium_seed203
1,508.09
30/30(100%)
142ms
scarce_couriers_seed401
3,110.45
20/40(50%)
96ms
small_seed100
663.37
15/15(100%)
61ms
tiny_seed42
305.11
6/6(100%)
53ms
本次会话提交历史
10:32:26
1,710.58
10/10 个算例


平均惩罚分数
2,910.00
完成算例
0 / 10
high_noise_seed601
3,000.00
❌ error
large_seed301
4,000.00
❌ error
large_seed302
4,000.00
❌ error
low_willingness_seed501
3,000.00
❌ error
medium_seed201
3,000.00
❌ error
medium_seed202
3,000.00
❌ error
medium_seed203
3,000.00
❌ error
scarce_couriers_seed401
4,000.00
❌ error
small_seed100
1,500.00
❌ error
tiny_seed42
600.00
❌ error

{
  "job_id": "fab359bd36874276a75f3dbf7edc172b",
  "status": "queued",
  "team": "router",
  "queue_depth": 1,
  "daily_remaining": 16,
  "daily_limit": 20,
  "poll_url": "/result/fab359bd36874276a75f3dbf7edc172b"
}
{
  "job_id": "fab359bd36874276a75f3dbf7edc172b",
  "status": "ok",
  "team": "router",
  "queued_at": "2026-05-08 00:39:47",
  "started_at": "2026-05-08 00:39:47",
  "finished_at": "2026-05-08 00:39:49",
  "avg_score": 2910.0,
  "case_count": 10,
  "success_count": 0,
  "case_results": [
    {
      "status": "error",
      "case_file": "high_noise_seed601.txt",
      "elapsed_ms": 62,
      "message": "运行时错误:\nTraceback (most recent call last):\n  File \"/tmp/tmpjps9p2j4.py\", line 62, in <module>\n  File \"/usr/local/python3.6.4/lib/python3.6/contextlib.py\", line 81, in __enter__\n  File \"/tmp/tmpjps9p2j4.py\", line 54, in __stickytape_temporary_dir\n  File \"/tmp/tmpjps9p2j4.py\", line 27, in _safe_import\nImportE",
      "penalty_score": 3000,
      "total_tasks": 30
    },
    {
      "status": "error",
      "case_file": "large_seed301.txt",
      "elapsed_ms": 61,
      "message": "运行时错误:\nTraceback (most recent call last):\n  File \"/tmp/tmpuog6f_w_.py\", line 62, in <module>\n  File \"/usr/local/python3.6.4/lib/python3.6/contextlib.py\", line 81, in __enter__\n  File \"/tmp/tmpuog6f_w_.py\", line 54, in __stickytape_temporary_dir\n  File \"/tmp/tmpuog6f_w_.py\", line 27, in _safe_import\nImportE",
      "penalty_score": 4000,
      "total_tasks": 40
    },
    {
      "status": "error",
      "case_file": "large_seed302.txt",
      "elapsed_ms": 63,
      "message": "运行时错误:\nTraceback (most recent call last):\n  File \"/tmp/tmpghlon2pv.py\", line 62, in <module>\n  File \"/usr/local/python3.6.4/lib/python3.6/contextlib.py\", line 81, in __enter__\n  File \"/tmp/tmpghlon2pv.py\", line 54, in __stickytape_temporary_dir\n  File \"/tmp/tmpghlon2pv.py\", line 27, in _safe_import\nImportE",
      "penalty_score": 4000,
      "total_tasks": 40
    },
    {
      "status": "error",
      "case_file": "low_willingness_seed501.txt",
      "elapsed_ms": 63,
      "message": "运行时错误:\nTraceback (most recent call last):\n  File \"/tmp/tmpf7bw_qal.py\", line 62, in <module>\n  File \"/usr/local/python3.6.4/lib/python3.6/contextlib.py\", line 81, in __enter__\n  File \"/tmp/tmpf7bw_qal.py\", line 54, in __stickytape_temporary_dir\n  File \"/tmp/tmpf7bw_qal.py\", line 27, in _safe_import\nImportE",
      "penalty_score": 3000,
      "total_tasks": 30
    },
    {
      "status": "error",
      "case_file": "medium_seed201.txt",
      "elapsed_ms": 61,
      "message": "运行时错误:\nTraceback (most recent call last):\n  File \"/tmp/tmppcdprjas.py\", line 62, in <module>\n  File \"/usr/local/python3.6.4/lib/python3.6/contextlib.py\", line 81, in __enter__\n  File \"/tmp/tmppcdprjas.py\", line 54, in __stickytape_temporary_dir\n  File \"/tmp/tmppcdprjas.py\", line 27, in _safe_import\nImportE",
      "penalty_score": 3000,
      "total_tasks": 30
    },
    {
      "status": "error",
      "case_file": "medium_seed202.txt",
      "elapsed_ms": 57,
      "message": "运行时错误:\nTraceback (most recent call last):\n  File \"/tmp/tmp_t15shad.py\", line 62, in <module>\n  File \"/usr/local/python3.6.4/lib/python3.6/contextlib.py\", line 81, in __enter__\n  File \"/tmp/tmp_t15shad.py\", line 54, in __stickytape_temporary_dir\n  File \"/tmp/tmp_t15shad.py\", line 27, in _safe_import\nImportE",
      "penalty_score": 3000,
      "total_tasks": 30
    },
    {
      "status": "error",
      "case_file": "medium_seed203.txt",
      "elapsed_ms": 59,
      "message": "运行时错误:\nTraceback (most recent call last):\n  File \"/tmp/tmpmr0rwixf.py\", line 62, in <module>\n  File \"/usr/local/python3.6.4/lib/python3.6/contextlib.py\", line 81, in __enter__\n  File \"/tmp/tmpmr0rwixf.py\", line 54, in __stickytape_temporary_dir\n  File \"/tmp/tmpmr0rwixf.py\", line 27, in _safe_import\nImportE",
      "penalty_score": 3000,
      "total_tasks": 30
    },
    {
      "status": "error",
      "case_file": "scarce_couriers_seed401.txt",
      "elapsed_ms": 59,
      "message": "运行时错误:\nTraceback (most recent call last):\n  File \"/tmp/tmp1f6jmyo2.py\", line 62, in <module>\n  File \"/usr/local/python3.6.4/lib/python3.6/contextlib.py\", line 81, in __enter__\n  File \"/tmp/tmp1f6jmyo2.py\", line 54, in __stickytape_temporary_dir\n  File \"/tmp/tmp1f6jmyo2.py\", line 27, in _safe_import\nImportE",
      "penalty_score": 4000,
      "total_tasks": 40
    },
    {
      "status": "error",
      "case_file": "small_seed100.txt",
      "elapsed_ms": 54,
      "message": "运行时错误:\nTraceback (most recent call last):\n  File \"/tmp/tmplr10bk7u.py\", line 62, in <module>\n  File \"/usr/local/python3.6.4/lib/python3.6/contextlib.py\", line 81, in __enter__\n  File \"/tmp/tmplr10bk7u.py\", line 54, in __stickytape_temporary_dir\n  File \"/tmp/tmplr10bk7u.py\", line 27, in _safe_import\nImportE",
      "penalty_score": 1500,
      "total_tasks": 15
    },
    {
      "status": "error",
      "case_file": "tiny_seed42.txt",
      "elapsed_ms": 62,
      "message": "运行时错误:\nTraceback (most recent call last):\n  File \"/tmp/tmppvo28tfv.py\", line 62, in <module>\n  File \"/usr/local/python3.6.4/lib/python3.6/contextlib.py\", line 81, in __enter__\n  File \"/tmp/tmppvo28tfv.py\", line 54, in __stickytape_temporary_dir\n  File \"/tmp/tmppvo28tfv.py\", line 27, in _safe_import\nImportE",
      "penalty_score": 600,
      "total_tasks": 6
    }
  ],
  "finished_ts": 1778171989.3341463
}