import argparse
from pathlib import Path
from time import perf_counter

from autosolver.evaluator import evaluate_solution
from autosolver.parser import format_output_rows, parse_problem, solution_to_output
from autosolver.solver import AutoSolver


def run_with_eval(instance, time_limit_seconds: float):
    solver = AutoSolver(time_limit_seconds=time_limit_seconds)
    started = perf_counter()
    solution = solver.solve(instance)
    wall_time = perf_counter() - started
    evaluation = evaluate_solution(instance, solution)
    return solver, solution, evaluation, wall_time


def print_eval_report(
    solver: AutoSolver,
    evaluation,
    wall_time: float,
    total_candidates: int,
    total_tasks: int,
    total_couriers: int,
) -> None:
    print("=" * 80)
    print("实例规模")
    print("-" * 80)
    print(f"  候选数:    {total_candidates}")
    print(f"  任务数:    {total_tasks}")
    print(f"  骑手数:    {total_couriers}")
    print()
    print("求解结果")
    print("-" * 80)
    print(f"  总用时:    {wall_time:.4f}s  (限制 {solver.time_limit_seconds}s)")
    print(f"  解有效性:  {'有效' if evaluation.valid else '无效'}")
    print(
        f"  期望覆盖:  {evaluation.expected_covered_tasks:.4f} / {total_tasks} "
        f"({evaluation.expected_coverage_rate:.2%})"
    )
    print(f"  总分:      {evaluation.total_score:.4f}")
    print(f"  分配成本:  {evaluation.assignment_cost:.4f}")
    print(
        f"  未分配罚分:{evaluation.unassigned_penalty:.4f} "
        f"({evaluation.unassigned_count} * 100)"
    )
    print(f"  原始分数:  {evaluation.raw_total_score:.4f}")
    print(f"  分配数:    {evaluation.assignment_count}")
    if evaluation.errors:
        print(f"  错误:")
        for err in evaluation.errors:
            print(f"    - {err}")
    print()
    print("策略历史")
    print("-" * 80)
    print(f"  {'#':<4} {'策略':<24} {'用时(s)':<6} {'有效':<6} {'改进':<6} {'期望覆盖':<10} {'总分':<12}")
    print(f"  {'—'*4} {'—'*25} {'—'*10} {'—'*6} {'—'*6} {'—'*10} {'—'*12}")
    for i, record in enumerate(solver.history, 1):
        print(
            f"  {i:<4} {record.strategy_name:<25} "
            f"{record.elapsed_seconds:<10.4f} "
            f"{'是' if record.valid else '否':<6} "
            f"{'是' if record.improved else '否':<6} "
            f"{record.covered_tasks:<10.4f} "
            f"{record.total_score:<12.4f}"
        )
        if record.error:
            print(f"        ⚠ {record.error}")
    print("=" * 80)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AutoSolver on a local input file.")
    parser.add_argument("case", type=Path, help="Path to a TSV case file.")
    parser.add_argument(
        "--time-limit",
        type=float,
        default=9.5,
        help="Time limit in seconds (default: 9.5).",
    )
    parser.add_argument(
        "--eval",
        action="store_true",
        default=False,
        help="Print evaluation report after solving.",
    )
    args = parser.parse_args()

    input_text = args.case.read_text(encoding="utf-8")
    instance = parse_problem(input_text)

    if args.eval:
        solver, solution, evaluation, wall_time = run_with_eval(
            instance, args.time_limit
        )
        print_eval_report(
            solver,
            evaluation,
            wall_time,
            total_candidates=len(instance.candidates),
            total_tasks=len(instance.task_ids),
            total_couriers=len(instance.courier_ids),
        )
        print()
        print("--- 输出 ---")
        formatted = format_output_rows(solution_to_output(solution))
        if formatted:
            print(formatted)
    else:
        solver = AutoSolver(time_limit_seconds=args.time_limit)
        solution = solver.solve(instance)
        formatted = format_output_rows(solution_to_output(solution))
        if formatted:
            print(formatted)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
