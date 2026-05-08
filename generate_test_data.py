"""
测试数据生成器
==============

生成符合竞赛格式的配送分配问题测试数据。

输入数据格式（TSV）：
    task_id_list    courier_id    total_score    willingness
    T0001           C000          10.5           0.75
    T0001,T0002     C001          21.3           0.60

生成模型：
    - 对每个骑手，先生成所有单任务候选项（num_tasks 个）
    - 再额外生成若干两任务包候选项，包内任务随机配对
    - 单任务分数 ~ Normal(score_mean, score_std)
    - 包分数 = 包内两任务分数之和
    - 接单意愿 = 骑手基础意愿 + 小幅随机扰动

用法：
    python generate_test_data.py                    # 使用默认配置生成到 data/ 目录
    python generate_test_data.py --output-dir cases/ # 指定输出目录
    python generate_test_data.py --cases 20          # 生成20个case
    python generate_test_data.py --seed 42           # 指定全局随机种子

    自定义参数示例：
    python generate_test_data.py --num-tasks 50 --num-couriers 100 --bundle-multiplier 5
    python generate_test_data.py --willingness-low 0.05 --willingness-high 0.3
    python generate_test_data.py --no-bundles        # 不生成两任务包

每个 case 是一个独立的 .txt 文件，文件名格式为 generated_{index}_seed{seed}.txt。
"""

import argparse
import math
import os
import random
import sys


# 每种 case 类型的默认参数
# 格式: (num_tasks, num_couriers, bundle_multiplier, score_mean, score_std, willingness_low, willingness_high)
# bundle_multiplier: 每个骑手的两任务包数量 = num_tasks * bundle_multiplier
CASE_PRESETS = {
    "tiny":              (6,  10, 0.0,  12.0, 2.0, 0.35, 0.90),
    "small":             (15, 25, 0.0,  12.0, 2.5, 0.20, 0.95),
    "medium":            (30, 60, 0.0,  11.0, 1.5, 0.10, 0.95),
    "large":             (40, 80, 9.25, 11.0, 1.0, 0.10, 0.95),
    "high_noise":        (30, 60, 0.0,  11.0, 3.0, 0.15, 0.95),
    "low_willingness":   (30, 60, 0.0,  11.0, 1.5, 0.05, 0.30),
    "scarce_couriers":   (40, 20, 0.0,  11.5, 1.5, 0.10, 0.95),
}


def _clamp(value, lo, hi):
    """将 value 限制在 [lo, hi] 区间内。"""
    return max(lo, min(hi, value))


def _format_id(prefix, num, width):
    """生成固定宽度的 ID，如 T0001, C0042。"""
    return "%s%0*d" % (prefix, width, num)


def _generate_base_scores(rng, num_tasks, score_mean, score_std, score_min, score_max):
    """
    为每个任务生成基础分数。
    基础分数 ~ Normal(score_mean, score_std)，截断到 [score_min, score_max]。
    """
    scores = []
    for _ in range(num_tasks):
        s = rng.gauss(score_mean, score_std)
        s = _clamp(s, score_min, score_max)
        scores.append(round(s, 4))
    return scores


def _build_candidates(rng, num_tasks, num_couriers, bundle_multiplier,
                      score_mean, score_std, score_min, score_max,
                      willingness_low, willingness_high,
                      task_width, courier_width):
    """
    生成所有候选项列表。

    模型：
      1. 每个骑手有 num_tasks 个单任务候选项（覆盖所有任务）
      2. 每个骑手额外有 round(num_tasks * bundle_multiplier) 个两任务包候选项
      3. 包内任务从所有任务中随机选取两个不同任务，按字典序排列

    返回候选项列表，每个元素为 (task_id_list_str, courier_id, total_score, willingness)。
    """
    base_scores = _generate_base_scores(rng, num_tasks, score_mean, score_std, score_min, score_max)

    task_ids = [_format_id("T", i, task_width) for i in range(num_tasks)]
    courier_ids = [_format_id("C", i, courier_width) for i in range(num_couriers)]

    candidates = []

    for ci in range(num_couriers):
        # 骑手基础意愿
        courier_w = rng.uniform(willingness_low, willingness_high)

        # 1. 单任务候选项：每个任务一个
        for ti in range(num_tasks):
            w = _clamp(courier_w + rng.gauss(0, 0.02), 0.01, 1.0)
            candidates.append((task_ids[ti], courier_ids[ci], base_scores[ti], round(w, 4)))

        # 2. 两任务包候选项
        num_bundles = round(num_tasks * bundle_multiplier)
        for _ in range(num_bundles):
            # 随机选两个不同任务
            ti = rng.randint(0, num_tasks - 1)
            tj = rng.randint(0, num_tasks - 2)
            if tj >= ti:
                tj += 1
            bundle_tasks = sorted([task_ids[ti], task_ids[tj]])
            task_str = ",".join(bundle_tasks)
            total_score = round(base_scores[ti] + base_scores[tj], 4)

            w = _clamp(courier_w + rng.gauss(0, 0.02), 0.01, 1.0)
            candidates.append((task_str, courier_ids[ci], total_score, round(w, 4)))

    return candidates


def generate_case(rng, num_tasks, num_couriers, bundle_multiplier=0.0,
                  score_mean=11.0, score_std=1.5,
                  score_min=10.0, score_max=100.0,
                  willingness_low=0.1, willingness_high=0.95):
    """
    生成单个测试用例。

    参数:
        rng:                random.Random 实例
        num_tasks:          任务数量
        num_couriers:       骑手数量
        bundle_multiplier:  每个骑手的包数量 = num_tasks * multiplier
        score_mean:         单任务分数均值
        score_std:          单任务分数标准差
        score_min:          单任务分数最小值
        score_max:          总分数最大值（截断）
        willingness_low:    接单意愿下界
        willingness_high:   接单意愿上界

    返回:
        TSV 格式的字符串（含表头）
    """
    task_width = max(4, len(str(num_tasks - 1)))
    courier_width = max(3, len(str(num_couriers - 1)))

    candidates = _build_candidates(
        rng, num_tasks, num_couriers, bundle_multiplier,
        score_mean, score_std, score_min, score_max,
        willingness_low, willingness_high,
        task_width, courier_width,
    )

    lines = ["task_id_list\tcourier_id\ttotal_score\twillingness"]
    for task_str, courier_id, score, w in candidates:
        lines.append("%s\t%s\t%s\t%s" % (task_str, courier_id, score, w))

    return "\n".join(lines) + "\n"


def _preset_to_config(preset):
    """将 preset 元组转为参数字典。"""
    keys = ["num_tasks", "num_couriers", "bundle_multiplier",
            "score_mean", "score_std", "willingness_low", "willingness_high"]
    return dict(zip(keys, preset))


def generate_cases(config, output_dir, num_cases, global_seed=None):
    """
    生成多个测试用例文件。

    参数:
        config:      用户自定义参数字典（覆盖预设）
        output_dir:  输出目录
        num_cases:   要生成的 case 数量
        global_seed: 全局随机种子（None 则随机）
    """
    os.makedirs(output_dir, exist_ok=True)

    if global_seed is not None:
        master_rng = random.Random(global_seed)
    else:
        master_rng = random.Random()

    preset_names = list(CASE_PRESETS.keys())

    for i in range(num_cases):
        # 循环使用 preset
        preset_name = preset_names[i % len(preset_names)]
        preset_config = _preset_to_config(CASE_PRESETS[preset_name])

        # 用户参数覆盖预设
        merged = dict(preset_config)
        merged.update({k: v for k, v in config.items() if v is not None})

        # 每个 case 使用独立的种子
        case_seed = master_rng.randint(0, 2**31 - 1)
        rng = random.Random(case_seed)

        content = generate_case(
            rng,
            num_tasks=merged["num_tasks"],
            num_couriers=merged["num_couriers"],
            bundle_multiplier=merged.get("bundle_multiplier", 0.0),
            score_mean=merged["score_mean"],
            score_std=merged["score_std"],
            score_min=merged.get("score_min", 10.0),
            score_max=merged.get("score_max", 100.0),
            willingness_low=merged["willingness_low"],
            willingness_high=merged["willingness_high"],
        )

        filename = "generated_%02d_seed%d.txt" % (i + 1, case_seed)
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        num_candidates = content.count("\n") - 2
        print("生成 %s: tasks=%d, couriers=%d, candidates=%d, seed=%d" % (
            filename, merged["num_tasks"], merged["num_couriers"],
            num_candidates, case_seed))


def main():
    preset_lines = []
    for k, v in CASE_PRESETS.items():
        preset_lines.append(
            "  %-20s tasks=%2d, couriers=%2d, bundle_mul=%.2f, "
            "score_mean=%.1f, score_std=%.1f, w=[%.2f, %.2f]"
            % (k, *v)
        )

    parser = argparse.ArgumentParser(
        description="生成配送分配问题测试数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="可用预设类型:\n" + "\n".join(preset_lines),
    )
    parser.add_argument("--cases", type=int, default=10,
                        help="生成的 case 数量（默认: 10）")
    parser.add_argument("--output-dir", type=str, default="data/generated",
                        help="输出目录（默认: data/generated）")
    parser.add_argument("--seed", type=int, default=None,
                        help="全局随机种子（默认: 随机）")

    # 可覆盖的参数
    parser.add_argument("--num-tasks", type=int, default=None,
                        help="任务数量（覆盖预设）")
    parser.add_argument("--num-couriers", type=int, default=None,
                        help="骑手数量（覆盖预设）")
    parser.add_argument("--bundle-multiplier", type=float, default=None,
                        help="包数量乘数，每骑手包数 = num_tasks * multiplier（覆盖预设）")
    parser.add_argument("--no-bundles", action="store_true",
                        help="不生成两任务包（等价于 --bundle-multiplier 0）")
    parser.add_argument("--score-mean", type=float, default=None,
                        help="单任务分数均值（覆盖预设）")
    parser.add_argument("--score-std", type=float, default=None,
                        help="单任务分数标准差（覆盖预设）")
    parser.add_argument("--score-min", type=float, default=None,
                        help="单任务分数最小值（默认: 10.0）")
    parser.add_argument("--score-max", type=float, default=None,
                        help="总分数最大值（默认: 100.0）")
    parser.add_argument("--willingness-low", type=float, default=None,
                        help="接单意愿下界（覆盖预设）")
    parser.add_argument("--willingness-high", type=float, default=None,
                        help="接单意愿上界（覆盖预设）")

    args = parser.parse_args()

    # 构建 config
    config = {}
    if args.num_tasks is not None:
        config["num_tasks"] = args.num_tasks
    if args.num_couriers is not None:
        config["num_couriers"] = args.num_couriers
    if args.no_bundles:
        config["bundle_multiplier"] = 0.0
    elif args.bundle_multiplier is not None:
        config["bundle_multiplier"] = args.bundle_multiplier
    if args.score_mean is not None:
        config["score_mean"] = args.score_mean
    if args.score_std is not None:
        config["score_std"] = args.score_std
    if args.score_min is not None:
        config["score_min"] = args.score_min
    if args.score_max is not None:
        config["score_max"] = args.score_max
    if args.willingness_low is not None:
        config["willingness_low"] = args.willingness_low
    if args.willingness_high is not None:
        config["willingness_high"] = args.willingness_high

    print("=" * 60)
    print("测试数据生成器")
    print("=" * 60)
    print("输出目录: %s" % args.output_dir)
    print("Case 数量: %d" % args.cases)
    print("全局种子: %s" % (args.seed if args.seed is not None else "随机"))
    if config:
        print("自定义参数: %s" % config)
    print("-" * 60)

    generate_cases(config, args.output_dir, args.cases, args.seed)

    print("-" * 60)
    print("完成！共生成 %d 个测试用例。" % args.cases)


if __name__ == "__main__":
    main()
