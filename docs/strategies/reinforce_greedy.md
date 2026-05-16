# ReinforceGreedy

源码位置：`autosolver/strategies/greedy_variants.py`

策略名：`reinforce_greedy`

## 实现逻辑

`ReinforceGreedy` 的设计意图是：在已有 `incumbent` 基础上，给已经选中的任务包追加未使用骑手，从而提高同一任务包的联合接单概率并降低该任务包的期望成本。

当前代码流程如下：

1. 如果 `incumbent` 为空或没有任何分配，直接返回空解。
2. 将 `incumbent.assignments` 复制为当前分配列表。
3. 收集已使用骑手 `used_couriers`。
4. 收集已分配订单 `assigned_tasks`。
5. 将所有未使用骑手的候选按骑手分组。
6. 将当前分配按 `task_id_list` 建成 `task_groups`。
7. 循环寻找能降低某个已有任务包组成本的候选：
   - 候选骑手必须未使用。
   - 候选任务包必须对应已有 `task_group`。
   - 用 `_group_assignment_cost(group)` 与 `_group_assignment_cost(group + [candidate])` 比较追加前后的成本。
   - 如果找到正向节省最大的候选，就追加到方案中。
8. 重复直到没有改进或时间预算耗尽。

## 不合理或欠佳点

- 当前实现存在逻辑冲突，导致策略基本不会追加任何候选：
  - 代码先检查 `if any(task_id in assigned_tasks for task_id in candidate.task_ids): continue`。
  - 但随后又要求 `task_groups.get(candidate.task_id_list)` 存在。
  - 如果候选属于已有任务包，它的订单必然已经在 `assigned_tasks` 中，因此会被提前跳过。
  - 如果候选不属于已有任务包，又无法通过 `task_groups` 检查。
- 因此，在当前代码下，该策略通常只是返回原 `incumbent` 的拷贝。
- 如果 `incumbent` 是 `None` 或空分配，策略直接返回空解，不会自己构造初始解。
- 即使修复上述冲突，策略也只会追加已有任务包的骑手，不会尝试新增任务包、替换任务包或删除有害分配。
- 节省计算只关注已有任务包组成本，不考虑追加骑手后对全局骑手资源的机会成本。
- `_group_assignment_cost()` 使用按概率加权的平均分数，追加一个高分但高概率骑手时，可能对成本产生非直观影响，需要谨慎验证。

## 表现尚可的 case

按当前实现，表现尚可的场景主要是“无需追加骑手，保持 incumbent 即可”的场景：

- 前序策略已经给出足够好的解。
- 同一任务包多骑手强化并不重要。
- 用户只希望该策略不破坏已有解。

如果修复订单冲突检查后，它可能适合：

- 同一任务包有多个候选骑手，且追加骑手能显著提高接单概率。
- 前序解已经选中了正确任务包，只是缺少冗余骑手。
- 骑手数量充足，追加骑手的机会成本较低。

## 表现会很差的 case

- 当前实现下，任何依赖“追加同包骑手”才能改进的 case 都会失败。
- `incumbent` 为空或质量很差时，策略没有独立构造能力。
- 最优解需要替换任务包，而不是给既有任务包加骑手。
- 骑手资源紧张，追加骑手会抢占其他更重要任务的机会。
- 成本改进依赖多个骑手一起追加，单次追加看不到收益。
