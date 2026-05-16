# GreedyByScore

源码位置：`autosolver/strategies/greedy.py`

策略名：`greedy_by_score`

## 实现逻辑

`GreedyByScore` 会先对所有候选分配排序，再按排序结果从前往后贪心选择。

排序键为：

```python
(
    candidate_assignment_cost(candidate),
    len(candidate.task_ids),
    candidate.task_id_list,
    candidate.courier_id,
    candidate.index,
)
```

其中 `candidate_assignment_cost()` 使用评估器中的单候选期望成本公式：

```text
p * total_score + (1 - p) * 100 * task_count
```

`p` 是裁剪到 `[0, 1]` 的 `willingness`，`task_count` 是任务包内订单数。

排序完成后，策略调用共享的 `build_greedy_solution()`：

1. 维护已使用骑手集合 `used_couriers`。
2. 维护已覆盖订单集合 `used_tasks`。
3. 依次遍历排序后的候选。
4. 如果候选骑手已被使用，则跳过。
5. 如果候选任务包中任一订单已被使用，则跳过。
6. 否则把该候选转成 `Assignment` 加入解，并占用骑手和订单。
7. 时间预算耗尽时提前停止。

该策略不读取 `incumbent`，每次都从空解开始构造。

## 不合理或欠佳点

- 名称叫 `GreedyByScore`，但实际排序第一关键字不是原始 `total_score`，而是单候选期望成本 `candidate_assignment_cost()`。这比名称更合理一些，但容易造成阅读误解。
- 贪心只看候选的局部排序结果，不计算加入该候选相对“不分配”的真实增量收益。若某个候选成本高于未分配罚分，策略仍可能在无冲突时选择它。
- `len(candidate.task_ids)` 是升序排序，同成本时会优先选更小任务包，可能提前占用订单并阻断更有价值的合单。
- `used_tasks` 会阻止同一任务包被多个骑手重复分配，因此无法利用评估器支持的“同一任务包多骑手联合接单概率”。
- 不会回滚早期选择。一个成本较低的单订单候选可能阻断一个整体更优的双订单候选。
- 不使用当前最优解，也不根据剩余候选动态调整排序。

## 表现尚可的 case

- 候选之间冲突较少，局部低成本选择很少阻断后续选择。
- 任务包主要是单订单，合单收益不明显。
- `willingness` 差异较大，且单候选期望成本能较好反映真实取舍。
- 大多数候选的 `total_score` 都低于对应的未分配罚分，选择更多合法候选通常不会显著变差。
- 需要非常快地产生一个稳定、合法、确定性的 baseline 解。

## 表现会很差的 case

- 存在大量重叠任务包，早期局部选择会阻断后续更优组合。
- 合单候选虽然单项成本略高，但整体能用更少骑手覆盖更多订单。
- 同一任务包分配给多个骑手能显著提升接单概率，但策略只能选其中一个。
- 存在高 `total_score` 或低 `willingness` 候选，其期望成本高于直接未分配。
- 最优解需要先牺牲局部低成本选择，才能换取全局更低总分。
