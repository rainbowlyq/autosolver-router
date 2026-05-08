# AutoSolver — 外卖配送分配问题求解器

## 问题背景

在外卖配送系统中，需要把配送订单分配给骑手。输入中的每个 `task_id_list` 已经是一个候选任务包，可能包含一个或多个订单；求解器只需要从这些候选任务包中选择分配，不需要自行重新组包。同一个订单最多只能出现在一个已选任务包中，且每个骑手最多只能被分配一次。骑手有概率拒绝订单，因此任务是否被覆盖要按接单概率计算，而不是只要分配就认为已覆盖。系统需要在多个目标之间取得平衡：**最大化期望接单订单数量**、**最小化期望系统总分数**，并通过输入中已有的合单候选来优化资源利用率。

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

1. **同一个订单最多只能被分配一次** — 若两个任务包包含同一个订单，则不能同时选择
2. **每个骑手最多被分配一次** — 同一个骑手编号只能在方案中出现一次
3. **只能使用候选集中存在的任务包-骑手分配** — 不能凭空编造不存在的组合，也不能自行根据订单重新组包

## 优化目标

按优先级从高到低：

1. **首要目标：最大化期望覆盖任务数** — 在各骑手接单事件相互独立的假设下，对任务 `t`，若已指派候选的接单概率为 `p1, p2, ...`，则 `P(t 被覆盖) = 1 - Π(1 - pi)`；总体期望覆盖数为所有任务覆盖概率之和
2. **次要目标：最小化期望总分数** — 在期望覆盖任务数相同的情况下，最小化 `Σ(total_score * willingness)`
3. **第三目标：最小化分配数** — 在以上两者相同的情况下，分配次数越少越好（合单更优）

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
- 本项目的 `solver.py` 就是该入口

## 当前实现策略

框架实现了 5 种求解策略，按顺序依次尝试，保留最优解：

### 策略 1：`GreedyByScore` — 按分数贪心

**行为**：将所有候选按 `total_score` 升序排列，然后依次遍历，只要该候选的骑手未被占用且包内订单未被其他已选候选覆盖，就将其加入方案。

**特点**：最直观，优先选分数低的分配。但不考虑合单，可能错过"一个骑手送两个单"更优的情况。

**排序规则**：`(total_score, 合单任务数, task_id_list, courier_id, 行号)`

### 策略 2：`GreedyByExpectedScore` — 按期望分数贪心

**行为**：将分数按骑手意愿归一化，按 `total_score / max(willingness, 0.01)` 升序排列，然后同样在骑手不重复的前提下贪心选取。

**特点**：优先选择"实际期望成本低"的分配。一个分数很低但骑手接单概率也很低的候选，归一化后分数会变高，从而被排到后面。

**排序规则**：`(total_score / willingness, total_score, task_id_list, courier_id, 行号)`

### 策略 3：`GreedyByCoverage` — 按覆盖数贪心

**行为**：优先选择合单（单次候选涉及任务数多）的候选，在合单任务数相同时，按每个任务的平均分数升序排列。

**特点**：倾向于用更少的骑手覆盖更多的任务，在任务数少、合单收益高的场景下表现更好。

**排序规则**：`(-合单任务数, total_score / 合单任务数, total_score, task_id_list, courier_id, 行号)`

### 策略 4：`ExactBranchAndBound` — 限时精确搜索

**行为**：按骑手分组，每个骑手选择 0 或 1 个候选分配，使用分支定界枚举合法组合。搜索过程中维护每个任务的未覆盖概率、当前期望覆盖数和期望分数，并用剩余骑手能触达的任务集合计算覆盖上界；如果上界不可能超过当前最优解，则剪枝。默认最多使用 0.5 秒内部时间预算，且不超过剩余全局预算的 10%。

**特点**：在小规模实例或剩余搜索空间可穷尽时返回精确最优解；在大规模实例中超时前返回已发现的最优解或传入的 incumbent。

### 策略 5：`LocalRepair` — 局部搜索修复

**行为**：以前面策略得到的最优解为起点，反复尝试**单次替换**：从当前方案中移除一个分配，然后从候选集中找一个不与剩余骑手冲突的候选加入，如果能改进期望目标则接受。重复直到无法改进或时间耗尽。如果前面没有产生有效解，则先用 `GreedyByScore` 生成初始解。

**特点**：能在贪心或精确搜索得到的 incumbent 基础上进一步优化，比纯贪心更精细。

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
│  策略 4: ExactBranchAndBound            │
│    → 评估 → 更新最优解 → 记录           │
│  策略 5: LocalRepair                    │
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
```

## 运行测试

```bash
# 全部测试
uv run python -m unittest discover -s tests -v

# 单个测试文件
uv run python -m unittest tests.test_evaluator -v
```

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
        greedy_variants.py   # GreedyByExpectedScore, GreedyByCoverage
        exact.py             # ExactBranchAndBound
        local_search.py      # LocalRepair
tests/                       # 单元测试
data/                        # 测试用例数据
```
