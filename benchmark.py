"""Benchmark the latest packed solver against all generated test cases."""
import glob
import importlib.util
import os
import sys
import time


def load_solver(path):
    """Load a solver module from a file path, returning the solve function."""
    spec = importlib.util.spec_from_file_location("solver_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.solve


def find_latest_solver(dist_dir="dist"):
    """Find the solver_{ts}.py with the largest timestamp in dist/."""
    pattern = os.path.join(dist_dir, "solver_*.py")
    files = glob.glob(pattern)
    if not files:
        print(f"No solver files found in {dist_dir}/ matching solver_*.py")
        sys.exit(1)
    # Sort by embedded timestamp (the numeric part after 'solver_')
    files.sort(key=lambda p: os.path.basename(p))
    latest = files[-1]
    return latest


def find_test_cases(data_dir="data/generated"):
    """Find all generated test case files."""
    pattern = os.path.join(data_dir, "generated_*.txt")
    files = sorted(glob.glob(pattern))
    return files


def run_benchmark():
    solver_path = find_latest_solver()
    solver_name = os.path.basename(solver_path)
    print(f"Solver: {solver_name}")
    print(f"{'=' * 80}")

    solve = load_solver(solver_path)
    test_files = find_test_cases()

    if not test_files:
        print("No test cases found in data/generated/")
        return

    results = []

    for fpath in test_files:
        fname = os.path.basename(fpath)
        with open(fpath, "r") as f:
            input_text = f.read()

        start = time.perf_counter()
        output = solve(input_text)
        elapsed = time.perf_counter() - start

        # Evaluate using the project's own evaluator
        from autosolver.parser import parse_problem
        from autosolver.evaluator import evaluate_solution
        from autosolver.models import Assignment, Solution

        instance = parse_problem(input_text)
        assignments = []
        for task_id_list_str, courier_ids in output:
            task_ids = tuple(t.strip() for t in task_id_list_str.split(","))
            # Find matching candidate index
            for cand in instance.candidates:
                if cand.task_id_list == task_id_list_str and cand.courier_id == courier_ids[0]:
                    assignments.append(Assignment(candidate=cand, courier_ids=tuple(courier_ids)))
                    break
        solution = Solution(assignments=tuple(assignments))
        ev = evaluate_solution(instance, solution)

        results.append({
            "file": fname,
            "valid": ev.valid,
            "total_score": ev.expected_total_score,
            "coverage_rate": ev.expected_coverage_rate,
            "covered_tasks": ev.expected_covered_tasks,
            "unassigned_count": ev.unassigned_count,
            "assignment_count": ev.assignment_count,
            "assignment_cost": ev.assignment_cost,
            "unassigned_penalty": ev.unassigned_penalty,
            "elapsed": elapsed,
        })

    # Print per-case results
    header = f"{'Case':<45} {'Valid':>5} {'Score':>12} {'Cov%':>7} {'Cov':>6} {'Unasgn':>6} {'AsgnCnt':>7} {'AsgnCost':>10} {'UnasgnPen':>10} {'Time':>7}"
    print(header)
    print("-" * len(header))

    for r in results:
        print(
            f"{r['file']:<45} "
            f"{'Y' if r['valid'] else 'N':>5} "
            f"{r['total_score']:>12.2f} "
            f"{r['coverage_rate'] * 100:>6.1f}% "
            f"{r['covered_tasks']:>6.1f} "
            f"{r['unassigned_count']:>6d} "
            f"{r['assignment_count']:>7d} "
            f"{r['assignment_cost']:>10.2f} "
            f"{r['unassigned_penalty']:>10.2f} "
            f"{r['elapsed']:>6.2f}s"
        )

    # Print averages
    n = len(results)
    avg_score = sum(r["total_score"] for r in results) / n
    avg_cov = sum(r["coverage_rate"] for r in results) / n
    avg_covered = sum(r["covered_tasks"] for r in results) / n
    avg_unassigned = sum(r["unassigned_count"] for r in results) / n
    avg_assignment_count = sum(r["assignment_count"] for r in results) / n
    avg_assignment_cost = sum(r["assignment_cost"] for r in results) / n
    avg_unassigned_pen = sum(r["unassigned_penalty"] for r in results) / n
    avg_time = sum(r["elapsed"] for r in results) / n

    print("-" * len(header))
    print(
        f"{'AVERAGE':<45} "
        f"{'':>5} "
        f"{avg_score:>12.2f} "
        f"{avg_cov * 100:>6.1f}% "
        f"{avg_covered:>6.1f} "
        f"{avg_unassigned:>6.1f} "
        f"{avg_assignment_count:>7.1f} "
        f"{avg_assignment_cost:>10.2f} "
        f"{avg_unassigned_pen:>10.2f} "
        f"{avg_time:>6.2f}s"
    )
    print(f"\n{n} test cases evaluated.")


if __name__ == "__main__":
    run_benchmark()
