## 项目概览

这是一个用于 AI Hackathon 竞赛的 **AutoSolver**。项目目标是求解配送分配问题：给定配送任务、可用骑手，以及预先计算好的分数和接单概率，寻找一种最优分配方案，在最大化期望任务覆盖数的同时，最小化期望总分数。

**竞赛约束：**
- 每个测试用例限时 10 秒
- 必须暴露 `solve(input_text: str) -> list`，返回 `[(task_id_list_str, [courier_id, ...]), ...]`
- 输入为 TSV，列包括：`task_id_list`、`courier_id`、`total_score`、`willingness`
- 同一个任务可以分配给多个骑手；骑手可能拒单，因此必须基于接单概率计算期望覆盖率，不能把任意分配都视为确定覆盖
- 每个骑手最多只能被分配一次
- 允许多任务候选项（例如 `T0001,T0002` 这样的任务包）

## 常用命令

```bash
# 运行全部测试
uv run python -m unittest discover -s tests -v

# 运行单个测试文件
uv run python -m unittest tests.test_evaluator -v

# 在本地样例文件上运行
uv run python run_local.py data/large_seed301.txt
```

本项目使用 `uv` 管理依赖和运行。开发阶段的依赖通过 `uv add --dev <package>` 添加（例如 `uv add --dev pytest`）。本地开发测试统一使用 `uv run` 命令运行。

## 评测环境约束

- **Python 3.6**：评测环境为 Python 3.6，不支持该版本之后引入的语法特性（如 f-string `=` 调试语法、walrus operator 在部分上下文中的限制等）。
- **纯标准库**：不允许引入任何第三方库，只能使用 Python 标准库。
- **单文件提交**：评测环境仅支持单个 `.py` 脚本文件提交，不支持多文件模块导入。提交前需将所有代码合并为一个文件。
- **禁止 `typing` 导入**：评测环境不支持导入 `typing` 库，所有类型注解需避免依赖 `typing`（如 `List`、`Tuple`、`Optional` 等），可使用 Python 3.6 内置语法（如 `list`、`tuple`）或不使用类型注解。

## 架构

### 入口点

- **`solver.py`**：竞赛入口点。定义 `solve(input_text: str) -> list`。这是一个薄封装：解析输入 -> 运行 AutoSolver -> 将解转换为输出列表。
- **`run_local.py`**：本地测试用 CLI 入口。接收一个文件路径参数，运行 `solve()`，并打印 TSV 输出。
- **`example_solver.py`**：基线贪心求解器（独立实现，不依赖框架）。可作为 I/O 契约参考。

### 核心包（`autosolver/`）

**数据模型**（`autosolver/models.py`）：
- `Candidate`：输入中的一行，包含任务包、骑手、分数和接单意愿。使用 `slots=True` 的不可变冻结 dataclass。
- `ProblemInstance`：包含所有候选项，以及派生出的有序 `task_ids` 和 `courier_ids`。通过 `from_candidates()` 创建。
- `Assignment`：解中的一个已选候选项。封装一个 `Candidate` 和 `courier_ids` 元组。
- `Solution`：按顺序保存的 `Assignment` 元组。空解使用 `Solution.empty()`。
- `AttemptRecord`：一次策略尝试的元数据，包括名称、耗时、有效性、是否改进、分数和错误信息。

**解析器**（`autosolver/parser.py`）：
- `parse_problem(input_text)` -> `ProblemInstance`。会跳过表头行、空行和格式错误的行。
- `solution_to_output(solution)` -> `list[tuple[str, list[str]]]`。转换为竞赛要求的输出格式。
- `format_output_rows(output)` -> TSV 字符串，用于打印。

**评估器**（`autosolver/evaluator.py`）：
- `evaluate_solution(instance, solution)` -> `Evaluation`。检查解的有效性（允许重复任务；重复骑手和未知候选项索引无效），并计算期望覆盖任务数、期望覆盖率、期望总分数、原始已分配分数、分配数量和确定性签名。假设骑手接单事件相互独立时，一个任务若被分配给接单概率为 `p1, p2, ...` 的多个骑手，其覆盖概率为 `1 - Π(1 - pi)`。
- `is_better_solution(instance, candidate, incumbent)` -> `bool`。按字典序比较目标：更高的期望覆盖任务数 -> 更低的期望总分数 -> 更少的分配数量 -> 字典序更小的签名。无效解永远不会胜出。

**时间预算**（`autosolver/budget.py`）：
- `TimeBudget(limit_seconds, safety_margin_seconds=0.05)`。使用 `perf_counter()`。主要方法包括：`expired()`、`remaining`、`has_time_for(seconds)`。

**策略协议**（`autosolver/strategies/base.py`）：
- `Strategy` 是一个 `Protocol`，包含 `name: str` 属性，以及 `run(instance, incumbent, budget) -> Solution` 方法。

**内置策略**（按 `StrategySelector` 注册顺序执行）：
1. `GreedyByScore`（`autosolver/strategies/greedy.py`）：按 `(total_score, bundle_size, task_id_list, courier_id, index)` 排序候选项。使用共享的 `build_greedy_solution()` 构建贪心解，保证骑手唯一；任务允许被多个骑手重复覆盖。
2. `GreedyByExpectedScore`（`autosolver/strategies/greedy_variants.py`）：按 `total_score / max(willingness, 0.01)` 排序。
3. `GreedyByCoverage`（`autosolver/strategies/greedy_variants.py`）：优先选择更大的任务包，排序键为 `(-bundle_size, score_per_task, total_score, ...)`。
4. `LocalRepair`（`autosolver/strategies/local_search.py`）：基于当前最优解尝试单点替换（移除一个分配，再插入一个不会复用剩余骑手的候选项）并迭代改进。如果没有当前最优解，则回退到 `GreedyByScore`。

**策略选择器**（`autosolver/selector.py`）：
- `StrategySelector` 保存有序策略元组。`next_strategy(history, budget)` 返回下一个未尝试策略（通过 `history` 的索引判断），如果时间预算已用尽或所有策略都已尝试，则返回 `None`。

**AutoSolver 循环**（`autosolver/solver.py`）：
- `AutoSolver(time_limit_seconds=9.5)`。其 `solve(instance)` 方法会：
  1. 创建 `TimeBudget`
  2. 循环执行：获取下一个策略 -> 运行策略 -> 评估结果 -> 若有改进则更新当前最优解 -> 记录尝试
  3. 捕获并记录异常，避免求解流程崩溃
  4. 返回找到的最佳解

### 测试结构

所有测试都位于 `tests/`，使用 `unittest`：
- `test_models.py`：数据模型构造和派生字段
- `test_parser.py`：TSV 解析边界情况和输出格式化
- `test_evaluator.py`：有效性检查、重复骑手检测、期望覆盖率计算、目标比较
- `test_strategies.py`：各策略都能产生有效解；本地修复策略保持或提升解质量
- `test_autosolver.py`：端到端 `solve` 能产生有效解；空输入返回空解
- `test_solver_contract.py`：顶层 `solve()` 函数返回正确形状

## 关键设计决策

- 目标函数采用字典序：最大化期望覆盖任务数 -> 最小化期望总分数 -> 最小化分配数量 -> 确定性地打破平局。重复任务分配是有效的，因为它只会按骑手接单概率以概率方式提升覆盖率。
- 框架是确定性的（不使用随机性），并且只依赖 Python 标准库。
- 策略选择是顺序且基于历史的，不是自适应的。选择器只会按顺序对每个策略尝试一次。
- 大型测试用例（`data/large_seed301.txt`）约有 33,780 个候选项、40 个任务、80 个骑手，任务包大小为 1 或 2。
