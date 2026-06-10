"""
Main entry point for the exact solver.
Delegates to exact_solver_v5 (column-generation MILP formulation).
"""
from exact_solver_v5 import solve_exact


def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: uv run main.py <input_file> [time_limit_s]")
        sys.exit(1)
    input_file = sys.argv[1]
    time_limit = float(sys.argv[2]) if len(sys.argv) > 2 else 300.0
    with open(input_file) as f:
        input_text = f.read()
    output = solve_exact(input_text, time_limit=time_limit)
    if output:
        print(f"\nOutput ({len(output)} assignments):")
        for til, cids in output:
            print(f"{til}\t{','.join(cids)}")
    else:
        print("No solution found.")


if __name__ == "__main__":
    main()
