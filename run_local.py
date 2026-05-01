from __future__ import annotations

import argparse
from pathlib import Path

from autosolver.parser import format_output_rows
from solver import solve


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AutoSolver on a local input file.")
    parser.add_argument("case", type=Path, help="Path to a TSV case file.")
    args = parser.parse_args()

    input_text = args.case.read_text(encoding="utf-8")
    output = solve(input_text)
    formatted = format_output_rows(output)
    if formatted:
        print(formatted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
