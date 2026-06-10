# AutoSolver — 外卖配送分配问题求解器

> [AutoSolver设计说明报告](docs/AutoSolver设计说明报告.pdf)

## 问题背景

在外卖配送系统中，需要把配送订单分配给骑手。输入中的每个 `task_id_list` 已经是一个候选任务包，可能包含一个或多个订单；求解器只需要从这些候选任务包中选择分配，不需要自行重新组包。同一个订单最多只能归属于一个已选任务包，但该任务包可以同时分配给一个或多个骑手；多个骑手接同一个任务包时，订单覆盖概率按联合接单概率提高。每个骑手最多只能被分配一次。骑手有概率拒绝订单，因此任务是否被覆盖要按接单概率计算，而不是只要分配就认为已覆盖。系统以**最小化期望总分**为核心目标，同时通过输入中已有的合单候选和同包多骑手补强来优化覆盖质量与资源利用率。

本项目参加的是一个 AI Hackathon 比赛，要求构建一个 **AutoSolver Agent 系统**，能够自主探索不同求解策略、自动评估与筛选、迭代改进，最终在时间限制内输出最优分配方案。

## 输入数据

输入是一个制表符分隔的文本文件（TSV），每行代表一个"候选分配"：

```
task_id_list    courier_id    total_score    willingness
T0001           C001          10.0           0.5
T0002           C002          11.0           0.5
T0001,T0002     C003          15.0           0.9
```

各列含义：

| 列名 | 含义 |
|------|------|
| `task_id_list` | 输入中给出的任务包编号列表。单任务包如 `T0001`，多任务包如 `T0001,T0002` |
| `courier_id` | 骑手编号 |
| `total_score` | 该分配的预计算分数，**越小越好** |
| `willingness` | 骑手接起该订单的概率（0~1），越高表示骑手越可能接单 |

## 约束条件

一个合法的分配方案必须满足：

1. **同一个订单最多只能归属于一个已选任务包** — 例如不能同时选择 `T0001,T0002` 和 `T0001,T0003`；但同一个任务包可以分配给多个骑手
2. **每个骑手最多被分配一次** — 同一个骑手编号只能在方案中出现一次
3. **只能使用候选集中存在的任务包-骑手分配** — 不能凭空编造不存在的组合，也不能自行根据订单重新组包

## 评分与优化目标

当前求解器以评估器计算出的 **期望总分最低** 为主目标。评分会显式考虑骑手拒单风险、同任务包多骑手的联合成功率，以及完全未分配订单的罚分。

单个任务包的成本为：

```text
任务包成本 = p_complete * expected_score + (1 - p_complete) * 100 * 任务包订单数
```

其中，同一个任务包分配给多个骑手时：

```text
p_complete = 1 - Π(1 - willingness_i)
```

总分为：

```text
总分 = 所有已选任务包成本之和 + 完全未分配订单数 * 100
```

方案比较顺序为：

1. **期望总分更低**
2. 总分相同，则 **分配数量更少**
3. 仍相同，则按确定性签名字典序比较，保证结果可复现

## 输出格式

```python
[(task_id_list_str, [courier_id, ...]), ...]
```

即一个列表，每个元素是一个 `(任务编号串, [骑手编号列表])` 的元组。例如：

```python
[("T0001,T0002", ["C003"]), ("T0003", ["C001"])]
```

输出时打印为 TSV 格式（`task_id_list<TAB>courier_id[,courier_id...]`），每行一个分配。

## 比赛限制

- **10 秒时间限制**：每个测试用例必须在 10 秒内完成求解
- **必须提供 `solve(input_text: str) -> list` 函数**：这是评测系统的调用入口
- **Python 3.6 + 标准库 + 单文件提交**：提交环境不依赖第三方库，也不支持多文件模块导入
- 本项目开发入口为 `solver.py`，提交前可通过 `pack.py` 打包为 `dist/solver_*.py`

## 当前实现策略

框架默认注册 13 种求解策略，按 `autosolver/selector.py` 中的顺序依次尝试。所有策略都受同一个时间预算约束，并通过同一个 `evaluate_solution()` 评分器竞争 incumbent。

### 1. 快速贪心

- `GreedyByScore`：按 `total_score` 升序快速构造初始解
- `GreedyByExpectedScore`：按 `total_score / max(willingness, 0.01)` 排序，降低低接单概率候选的优先级
- `GreedyByCoverage`：优先选择任务包更大的候选，在合单收益明显时更有优势

### 2. 覆盖感知贪心

- `GreedyCoverageAware`：按候选期望成本构造不重叠任务包方案
- `PressureCoverageGreedy`：根据任务稀缺度和最低可达成本计算压力，优先处理容易漏掉或代价高的任务

### 3. 单任务匹配

- `SingletonMatchingGreedy`：在单任务包场景下构造最小费用流式匹配，再用补强策略提高接单成功率
- `SingletonBeamReassignment`：在较小单任务实例上用束搜索尝试更好的任务-骑手重分配

### 4. 合单与搜索

- `BeamSetPackingSearch`：把候选任务包视为集合打包问题，在规模门控内用束搜索寻找不重叠组合
- `ExactBranchAndBound`：限时分支定界搜索，默认最多使用 0.5 秒且不超过剩余预算的一部分

### 5. 补强与局部修复

- `MarginalSavingsGreedy`：用相对未分配罚分的边际节省选择候选，也允许给同任务包增加骑手
- `ReinforceGreedy`：基于已有解，给同一个任务包补充仍可用且能降低期望成本的骑手
- `PairSwapRepair`：尝试两个已分配任务包之间交换骑手，默认最多局部搜索 2 秒
- `LocalRepair`：尝试移除一个分配并加入一个不冲突候选，持续进行单点替换改进

## 求解流程

```
输入 TSV 文本
    │
    ▼
解析为 ProblemInstance（候选集 + 任务列表 + 骑手列表）
    │
    ▼
┌─────────────────────────────────────────┐
│  时间预算循环（默认 9.5 秒）              │
│                                         │
│  策略 1: GreedyByScore                  │
│    → 评估 → 更新最优解 → 记录           │
│  策略 2: GreedyByExpectedScore          │
│    → 评估 → 更新最优解 → 记录           │
│  策略 3: GreedyByCoverage               │
│    → 评估 → 更新最优解 → 记录           │
│  ...                                    │
│  覆盖感知 / 匹配 / 束搜索 / 精确搜索     │
│    → 评估 → 更新最优解 → 记录           │
│  补强与局部修复策略                      │
│    → 评估 → 更新最优解 → 记录           │
│                                         │
│  时间耗尽或所有策略执行完毕 → 退出       │
└─────────────────────────────────────────┘
    │
    ▼
输出最优分配方案
```

## 本地运行

```bash
# 只输出分配结果
uv run python run_local.py data/large_seed301.txt

# 输出评测报告 + 分配结果
uv run python run_local.py data/large_seed301.txt --eval

# 自定义时间限制
uv run python run_local.py data/large_seed301.txt --eval --time-limit 5.0

# 打包为比赛提交用单文件
uv run python pack.py
```

## 运行测试

```bash
# 全部测试
uv run python -m unittest discover -s tests -v

# 单个测试文件
uv run python -m unittest tests.test_evaluator -v
```

## 离线参考求解

`solver-workspace/` 是独立的现代 Python 离线求解工作区，可使用 Gurobi 等第三方优化器生成近优参考解。该目录不受比赛提交环境的 Python 3.6、纯标准库、单文件和 10 秒限制约束，主要用于把参考结果保存到 `data/gurobi/` 或相关验证目录，帮助判断当前启发式策略距离近优解的差距。

提交版求解器仍坚持轻量启发式设计：标准库、限时运行、随时可返回当前最优合法解。

## 项目结构

```
solver.py                    # 比赛入口，定义 solve() 函数
run_local.py                 # 本地运行和评测入口
example_solver.py            # 贪心基线参考实现
autosolver/
    __init__.py              # 包导出
    models.py                # 数据模型（Candidate, ProblemInstance, Assignment, Solution）
    parser.py                # TSV 解析和输出格式化
    evaluator.py             # 解的评估和比较
    budget.py                # 时间预算管理
    selector.py              # 策略选择器
    solver.py                # AutoSolver 主循环
    strategies/
        __init__.py          # 策略导出
        base.py              # Strategy 协议定义
        greedy.py            # GreedyByScore + 共享贪心构建函数
        greedy_variants.py   # 贪心变体、匹配、束搜索和补强策略
        exact.py             # ExactBranchAndBound
        local_search.py      # PairSwapRepair, LocalRepair
pack.py                      # 生成比赛提交用单文件
pack_template.py             # 单文件打包模板
eval.py                      # 线上结果分析和报表辅助
benchmark.py                 # 本地基准辅助
tests/                       # 单元测试
data/                        # 测试用例数据
docs/                        # 设计报告和策略文档
solver-workspace/            # 离线参考求解工作区
```
