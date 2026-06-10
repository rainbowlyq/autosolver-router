"""Batch runner for offline Gurobi reference solutions.

Run from solver-workspace:

    uv run python run_gurobi_batch.py

By default this reads ../data/generated/*.txt, writes solution files to
../data/gurobi/, and writes summary.csv with both solver stats and evaluator
scores.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

from exact_solver_v5 import solve_file


SUMMARY_COLUMNS = [
    "case_file",
    "output_file",
    "valid",
    "total_score",
    "unassigned_count",
    "assignment_count",
    "solver_assignments",
    "iterations",
    "stop_reason",
    "initial_columns",
    "final_columns",
    "solver_seconds",
    "local_improvement_seconds",
    "elapsed_seconds",
    "errors",
]


def _load_project_evaluator(repo_root):
    repo_root = Path(repo_root).resolve()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from autosolver.evaluator import evaluate_solution
    from autosolver.models import Assignment, Solution
    from autosolver.parser import parse_problem

    return parse_problem, Assignment, Solution, evaluate_solution


def evaluate_output(case_path, output_path, repo_root):
    parse_problem, Assignment, Solution, evaluate_solution = _load_project_evaluator(repo_root)
    instance = parse_problem(case_path.read_text(encoding="utf-8"))

    by_key = {}
    for candidate in instance.candidates:
        by_key.setdefault((candidate.task_id_list, candidate.courier_id), candidate)

    assignments = []
    errors = []
    if not output_path.exists():
        return {
            "valid": False,
            "total_score": "",
            "unassigned_count": "",
            "assignment_count": "",
            "errors": "missing output",
        }

    for line_no, line in enumerate(output_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            errors.append("line {0}: malformed".format(line_no))
            continue
        task_id_list, courier_text = parts
        for courier_id in [part for part in courier_text.split(",") if part]:
            candidate = by_key.get((task_id_list, courier_id))
            if candidate is None:
                errors.append("line {0}: unknown ({1}, {2})".format(
                    line_no, task_id_list, courier_id
                ))
            else:
                assignments.append(Assignment(candidate, (courier_id,)))

    evaluation = evaluate_solution(instance, Solution(tuple(assignments)))
    all_errors = list(errors) + list(evaluation.errors)
    return {
        "valid": evaluation.valid and not errors,
        "total_score": "{0:.12f}".format(evaluation.expected_total_score),
        "unassigned_count": evaluation.unassigned_count,
        "assignment_count": evaluation.assignment_count,
        "errors": "; ".join(all_errors),
    }


def write_summary(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_batch(args):
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    repo_root = Path(args.repo_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    case_files = sorted(input_dir.glob(args.pattern))
    if not case_files:
        raise SystemExit("No input files matched {0} in {1}".format(args.pattern, input_dir))

    rows = []
    for index, case_path in enumerate(case_files, 1):
        print("\n=== [{0}/{1}] {2} ===".format(index, len(case_files), case_path.name))
        output_path = output_dir / case_path.name
        started = time.time()

        output, stats = solve_file(
            case_path,
            output_path,
            time_limit=args.time_limit,
            mip_gap=args.mip_gap,
            max_iterations=args.max_iterations,
            stall_iterations=args.stall_iterations,
            min_round_seconds=args.min_round_seconds,
            verbose=not args.quiet,
            return_stats=True,
        )
        elapsed = time.time() - started
        evaluation = evaluate_output(case_path, output_path, repo_root)

        row = {
            "case_file": case_path.name,
            "output_file": output_path.name,
            "solver_assignments": len(output),
            "iterations": stats["iterations"],
            "stop_reason": stats["stop_reason"],
            "initial_columns": stats["initial_columns"],
            "final_columns": stats["final_columns"],
            "solver_seconds": "{0:.3f}".format(stats["total_seconds"]),
            "local_improvement_seconds": "{0:.3f}".format(stats["local_improvement_seconds"]),
            "elapsed_seconds": "{0:.3f}".format(elapsed),
        }
        row.update(evaluation)
        rows.append(row)

        print(
            "Saved {0}: valid={1}, score={2}, iterations={3}, time={4}s".format(
                output_path,
                row["valid"],
                row["total_score"],
                row["iterations"],
                row["elapsed_seconds"],
            )
        )

    summary_path = output_dir / args.summary_name
    write_summary(summary_path, rows)
    print("\nSummary: {0}".format(summary_path))
    return rows


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Generate offline Gurobi reference outputs.")
    parser.add_argument("--input-dir", default="../data/generated")
    parser.add_argument("--output-dir", default="../data/gurobi")
    parser.add_argument("--repo-root", default="..")
    parser.add_argument("--pattern", default="generated_*.txt")
    parser.add_argument("--summary-name", default="summary.csv")
    parser.add_argument("--time-limit", type=float, default=120.0)
    parser.add_argument("--mip-gap", type=float, default=1e-6)
    parser.add_argument("--max-iterations", type=int, default=8)
    parser.add_argument("--stall-iterations", type=int, default=3)
    parser.add_argument("--min-round-seconds", type=float, default=30.0)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:
        pass
    run_batch(parse_args(argv))


if __name__ == "__main__":
    main(sys.argv[1:])
