# GreedyByExpectedScore

源码位置：`autosolver/strategies/greedy_variants.py`

策略名：`greedy_by_expected_score`

## 实现逻辑

`GreedyByExpectedScore` 会按 `total_score / max(willingness, 0.01)` 对候选分配排序，然后执行一次贪心选择。

排序键为：

```python
(
    candidate.total_score / max(candidate.willingness, 0.01),
    candidate.total_score,
    candidate.task_id_list,
    candidate.courier_id,
    candidate.index,
)
```

`max(willingness, 0.01)` 用来避免接单概率为 0 时除零。这个指标会惩罚低接单概率候选：同样的 `total_score` 下，`willingness` 越低，排序值越大。

排序后调用 `_build_unique_task_package_solution()` 构造解：

1. 维护已使用骑手集合 `used_couriers`。
2. 维护已使用任务包集合 `used_task_packages`。
3. 维护已覆盖订单集合 `used_tasks`。
4. 依次遍历候选。
5. 如果骑手已使用、任务包已使用、或任务包内任一订单已被其他任务包覆盖，则跳过。
6. 否则选择该候选。
7. 时间预算耗尽时提前停止。

该策略不读取 `incumbent`，每次都从空解开始构造。

## 不合理或欠佳点

- `total_score / willingness` 不是评估器的真实目标函数。真实单候选成本是 `p * total_score + (1 - p) * 100 * task_count`，还包含拒单后的罚分和任务包大小。
- 对 `willingness < 0.01` 的候选统一按 0.01 处理，会压平极低概率候选之间的差异。
- 排序没有显式考虑 `task_count`。一个单订单候选和一个双订单候选可能被放在同一尺度比较，导致覆盖效率判断失真。
- 构造解时仍然是“一次排序 + 不回滚”的贪心，不能修正早期错误选择。
- `_build_unique_task_package_solution()` 禁止同一任务包出现多次，所以不能给同一任务包追加多个骑手以提高联合接单概率。
- 只要候选不冲突就会加入，不会判断该候选是否比保持未分配更好。

## 表现尚可的 case

- 任务包大小基本一致，主要差异来自 `total_score` 和 `willingness`。
- 低接单概率候选确实应该被显著延后。
- 候选冲突较少，贪心顺序对全局结果影响不大。
- 数据中高分候选大多也有较高接单概率，`score / willingness` 能近似区分性价比。
- 需要快速得到一个比纯原始分数更重视接单概率的 baseline。

## 表现会很差的 case

- 任务包大小差异大，双订单或多订单候选的覆盖收益被指标低估或高估。
- `total_score` 高于未分配罚分时，策略仍可能因为无冲突而选择有害候选。
- 同一任务包需要多个骑手共同提高接单概率。
- 低 `willingness` 但极低 `total_score` 的候选在真实期望成本下可能仍可接受，但会被该比例指标强烈惩罚。
- 最优解依赖多个候选之间的组合关系，而不是单候选的分数/概率比值。
