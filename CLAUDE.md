# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working on code in this repository.

## Project Overview

This is an **AutoSolver** for a Kaggle/AI Hackathon competition. The goal is to solve a delivery assignment problem: given delivery tasks and available couriers with precomputed scores and acceptance probabilities, find an optimal assignment that maximizes expected task coverage while minimizing expected total score.

**Competition constraints:**
- 10-second time limit per test case
- Must expose `solve(input_text: str) -> list` returning `[(task_id_list_str, [courier_id, ...]), ...]`
- Input is TSV with columns: `task_id_list`, `courier_id`, `total_score`, `willingness`
- The same task may be assigned to multiple couriers; couriers can reject orders, so expected coverage must be computed from acceptance probabilities instead of treating any assignment as guaranteed coverage
- Each courier can be assigned at most once
- Multi-task candidates (bundles like `T0001,T0002`) are allowed

## Commands

```bash
# Run all tests
uv run python -m unittest discover -s tests -v

# Run a single test file
uv run python -m unittest tests.test_evaluator -v

# Run on a local case file
uv run python run_local.py data/large_seed301.txt
```

The project uses `uv` for dependency management. Dev dependency: `pytest>=9.0.3`.

## Architecture

### Entry Points

- **`solver.py`** — Competition entry point. Defines `solve(input_text: str) -> list`. Thin wrapper: parses input → runs AutoSolver → converts solution to output list.
- **`run_local.py`** — CLI runner for local testing. Takes a file path argument, runs `solve()`, prints TSV output.
- **`example_solver.py`** — Baseline greedy solver (standalone, no framework). Reference for the I/O contract.

### Core Package (`autosolver/`)

**Data models** (`autosolver/models.py`):
- `Candidate` — A row from the input: task bundle, courier, score, willingness. Immutable frozen dataclass with `slots=True`.
- `ProblemInstance` — All candidates plus derived sorted `task_ids` and `courier_ids`. Created via `from_candidates()`.
- `Assignment` — A chosen candidate in a solution. Wraps a `Candidate` with `courier_ids` tuple.
- `Solution` — Ordered tuple of `Assignment`s. `Solution.empty()` for empty.
- `AttemptRecord` — Metadata from one strategy attempt (name, time, validity, improvement, score, errors).

**Parser** (`autosolver/parser.py`):
- `parse_problem(input_text)` → `ProblemInstance`. Skips header row, empty lines, malformed rows.
- `solution_to_output(solution)` → `list[tuple[str, list[str]]]`. Competition output format.
- `format_output_rows(output)` → TSV string for printing.

**Evaluator** (`autosolver/evaluator.py`):
- `evaluate_solution(instance, solution)` → `Evaluation`. Checks validity (duplicate tasks are allowed; duplicate couriers and unknown candidate indexes are invalid), computes expected covered task count, expected coverage rate, expected total score, raw assigned score, assignment count, and a deterministic signature. Assuming independent courier acceptance events, a task with assigned acceptance probabilities `p1, p2, ...` has coverage `1 - Π(1 - pi)`.
- `is_better_solution(instance, candidate, incumbent)` → `bool`. Lexicographic comparison: higher expected covered tasks → lower expected total score → fewer assignments → lexicographically smaller signature. Invalid solutions never win.

**Time Budget** (`autosolver/budget.py`):
- `TimeBudget(limit_seconds, safety_margin_seconds=0.05)`. Uses `perf_counter()`. Key methods: `expired()`, `remaining`, `has_time_for(seconds)`.

**Strategy Protocol** (`autosolver/strategies/base.py`):
- `Strategy` is a `Protocol` with a `name: str` attribute and `run(instance, incumbent, budget) -> Solution`.

**Built-in Strategies** (registered in order by `StrategySelector`):
1. `GreedyByScore` (`autosolver/strategies/greedy.py`) — Sorts candidates by `(total_score, bundle_size, task_id_list, courier_id, index)`. Uses shared `build_greedy_solution()` which greedily picks candidates while keeping couriers unique; tasks may repeat across couriers.
2. `GreedyByExpectedScore` (`autosolver/strategies/greedy_variants.py`) — Sorts by `total_score / max(willingness, 0.01)`.
3. `GreedyByCoverage` (`autosolver/strategies/greedy_variants.py`) — Prefers larger bundles first: sorts by `(-bundle_size, score_per_task, total_score, ...)`.
4. `LocalRepair` (`autosolver/strategies/local_search.py`) — Takes the incumbent solution and tries single replacements (remove one assignment, insert one candidate without reusing a remaining courier) to iteratively improve. Falls back to `GreedyByScore` if no incumbent.

**Strategy Selector** (`autosolver/selector.py`):
- `StrategySelector` holds the ordered tuple of strategies. `next_strategy(history, budget)` returns the next untried strategy (by index into history) or `None` if budget expired or all strategies exhausted.

**AutoSolver Loop** (`autosolver/solver.py`):
- `AutoSolver(time_limit_seconds=9.5)`. The `solve(instance)` method:
  1. Creates a `TimeBudget`
  2. Loops: get next strategy → run it → evaluate → update incumbent if improved → record attempt
  3. Catches and records exceptions without crashing
  4. Returns the best solution found

### Test Structure

All tests are in `tests/` using `unittest`:
- `test_models.py` — Data model construction and derived fields
- `test_parser.py` — TSV parsing edge cases, output formatting
- `test_evaluator.py` — Validity checks, duplicate courier detection, expected coverage math, objective comparison
- `test_strategies.py` — Each strategy produces valid solutions; local repair preserves/improves
- `test_autosolver.py` — End-to-end solve produces valid solution; empty input returns empty
- `test_solver_contract.py` — Top-level `solve()` function returns correct shape

## Key Design Decisions

- All data classes are `frozen=True, slots=True` for immutability and memory efficiency.
- The objective is lexicographic: maximize expected covered tasks → minimize expected total score → minimize assignment count → deterministic tiebreaking. Duplicate task assignments are valid because they increase coverage only probabilistically according to rider acceptance probability.
- The framework is deterministic (no randomness) and uses only the Python standard library.
- Strategy selection is sequential and history-based, not adaptive. The selector simply tries each strategy once in order.
- The large test case (`data/large_seed301.txt`) has ~33,780 candidates, 40 tasks, 80 couriers, with bundle sizes of 1 or 2.
