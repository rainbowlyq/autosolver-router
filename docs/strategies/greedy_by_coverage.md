# GreedyByCoverage

源码位置：`autosolver/strategies/greedy_variants.py`

策略名：`greedy_by_coverage`

## 实现逻辑

`GreedyByCoverage` 先按任务包覆盖订单数排序，优先选择订单数更多的任务包。

排序键为：

```python
(
    -len(candidate.task_ids),
    candidate.total_score / len(candidate.task_ids),
    candidate.total_score,
    candidate.task_id_list,
    candidate.courier_id,
    candidate.index,
)
```

含义是：

1. 任务包越大越靠前。
2. 同样大小时，按单订单平均 `total_score` 越低越靠前。
3. 再用原始 `total_score` 和稳定字段打破平局。

排序后同样调用 `_build_unique_task_package_solution()`：

1. 骑手不能重复。
2. 同一 `task_id_list` 不能重复。
3. 不同任务包之间不能复用订单。
4. 满足约束的候选被立即加入解。
5. 时间预算耗尽时提前停止。

该策略不读取 `incumbent`。

## 不合理或欠佳点

- 覆盖订单数是排序第一关键字，优先级高于成本和接单概率。一个很差的大任务包可能压过多个明显更好的小任务包。
- 排序完全不看 `willingness`。低接单概率的大包会被过度偏好。
- 使用 `total_score / task_count` 近似单位覆盖成本，但真实评估还包含拒单概率和未分配罚分。
- 不能重复选择同一任务包，因此无法用多个骑手提高同一任务包的成功覆盖概率。
- 一旦大任务包被选中，它会占用包内所有订单，后续所有重叠候选都被排除。
- 不判断“选中候选”是否比“保持未分配”更优。

## 表现尚可的 case

- 合单候选质量普遍较好，且大任务包通常确实比多个小任务包更划算。
- 骑手接单概率较均匀，`willingness` 不是主要决策因素。
- 任务数量少，优先覆盖更多订单能快速构造可接受解。
- 骑手资源紧张，需要用有限骑手尽可能覆盖更多订单。
- 任务包之间重叠较少，大包选择不太会阻断更优组合。

## 表现会很差的 case

- 大任务包 `willingness` 很低或 `total_score` 很高。
- 两个或多个小任务包的总成本低于一个大任务包，但大任务包因覆盖数优先被先选。
- 大任务包和很多小任务包重叠，早期选择造成严重阻断。
- 任务包大小只是输入候选的偶然结果，并不代表真实收益。
- 最优解需要对大包和小包做精细组合，而不是一律偏好大包。
