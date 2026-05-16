# GreedyCoverageAware

源码位置：`autosolver/strategies/greedy_variants.py`

策略名：`greedy_coverage_aware`

## 实现逻辑

`GreedyCoverageAware` 先按任务包大小把候选分组，再从大任务包到小任务包依次选择。

主要流程：

1. 用 `defaultdict(list)` 将候选按 `len(candidate.task_ids)` 分组。
2. 每个大小组内按以下键排序：

   ```python
   (
       candidate_assignment_cost(candidate),
       candidate.task_id_list,
       candidate.courier_id,
       candidate.index,
   )
   ```

3. 按任务包大小从大到小遍历分组。
4. 维护已使用骑手集合 `used_couriers` 和已覆盖订单集合 `covered_tasks`。
5. 对每个候选，如果骑手未使用，且候选任务包与 `covered_tasks` 没有交集，就加入解。
6. 时间预算耗尽时提前停止。

它与 `GreedyByCoverage` 的区别是：同样优先大任务包，但组内排序使用评估器的单候选期望成本 `candidate_assignment_cost()`，而不是原始平均分。

该策略不读取 `incumbent`。

## 不合理或欠佳点

- 任务包大小仍然是最高优先级。即使小任务包成本明显更低，也要等所有更大包处理完才有机会被选。
- `candidate_assignment_cost()` 是单候选成本，不能表达多个候选组合后的全局收益。
- 只要候选不冲突就会加入，未检查加入后是否比保持未分配更好。
- 使用 `covered_tasks` 阻止任何订单重复，因此无法给同一任务包追加第二个骑手。
- 大任务包一旦被选中，会一次性锁定多个订单，后续没有回滚机制。
- 按大小分组后逐组扫描，仍然无法比较“大包高成本”和“小包低成本”的跨组取舍。

## 表现尚可的 case

- 大任务包通常质量好，且合单收益稳定。
- 同一大小任务包之间差异主要由 `candidate_assignment_cost()` 决定。
- 骑手数量偏少，需要优先考虑单个骑手覆盖更多订单。
- 输入候选主要是大小为 1 或 2 的包，大包偏好不会造成过大搜索偏差。
- 需要比 `GreedyByCoverage` 稍微更重视接单概率和拒单成本。

## 表现会很差的 case

- 大任务包成本明显高于小任务包组合。
- 大任务包接单概率很低，真实覆盖效果差。
- 最优解需要放弃一个大包，改选多个小包。
- 同一任务包多骑手联合接单很关键。
- 候选间重叠密集，早期大包选择会阻断大量后续优质候选。
