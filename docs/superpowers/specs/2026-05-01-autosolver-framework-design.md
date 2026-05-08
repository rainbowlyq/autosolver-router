# AutoSolver Framework Design

Date: 2026-05-01

## Context

This project targets the AutoSolver competition described in `docs/problem.md`.
The submitted solver must expose:

```python
def solve(input_text: str) -> list:
    ...
```

The return value must match `example_solver.py`:

```python
[(task_id_list_str, [courier_id, ...]), ...]
```

The input is tab-separated text with the columns:

- `task_id_list`
- `courier_id`
- `total_score`
- `willingness`

The observed large case `data/large_seed301.txt` has 33,780 candidate rows, 40 unique tasks, 80 couriers, and candidate bundle sizes of 1 or 2 tasks. The framework must preserve the submission contract while making it easy to add multiple solving strategies and an outer iterative selection loop.

## Goals

- Keep a stable `solve(input_text: str) -> list` entry point compatible with the baseline.
- Build a modular core that supports multiple strategy implementations.
- Add an agentic loop that tries strategies, evaluates results, tracks history, and returns the best solution found within the time budget.
- Provide a simple local runner for testing on `data/*.txt`.
- Keep the first version deterministic, dependency-light, and suitable for a 10 second per-case limit.

## Non-Goals

- Do not introduce an LLM dependency in the first scaffold.
- Do not build a full experiment database or reporting system.
- Do not change the input/output contract from `example_solver.py`.
- Do not require external solvers such as OR-Tools or commercial ILP engines in the initial framework.

## Recommended Architecture

Use a hybrid structure:

- A top-level `solver.py` for competition submission compatibility.
- A package `autosolver/` containing parsing, models, evaluation, strategy selection, budgeting, and strategy implementations.
- A lightweight CLI runner `run_local.py` for local files.
- Focused tests for parser, evaluator, and submission contract.

Planned structure:

```text
AI-Hackathon-AutoSolver/
├─ example_solver.py
├─ solver.py
├─ run_local.py
├─ docs/
│  ├─ superpowers/
│  └─ problem.md
├─ data/
│  ├─ large_seed301.txt
│  └─ example_solution.txt
├─ autosolver/
│  ├─ __init__.py
│  ├─ models.py
│  ├─ parser.py
│  ├─ evaluator.py
│  ├─ solver.py
│  ├─ selector.py
│  ├─ budget.py
│  └─ strategies/
│     ├─ __init__.py
│     ├─ base.py
│     ├─ greedy.py
│     ├─ greedy_variants.py
│     └─ local_search.py
└─ tests/
   ├─ test_parser.py
   ├─ test_evaluator.py
   └─ test_solver_contract.py
```

## Core Components

### Models

`autosolver.models` defines small data classes:

- `Candidate`: one input row containing task ids, original `task_id_list` string, courier id, score, willingness, and row index.
- `ProblemInstance`: all candidates plus derived task and courier sets.
- `Assignment`: one selected bundle and its assigned courier ids.
- `Solution`: assignments plus cached objective values when useful.
- `AttemptRecord`: strategy name, parameters, elapsed time, objective, validity, and whether the attempt improved the incumbent.

### Parser

`autosolver.parser` is responsible for all format handling:

- `parse_problem(input_text: str) -> ProblemInstance`
- `solution_to_output(solution: Solution) -> list`
- `format_output_rows(output: list) -> str`

Parsing should tolerate empty lines and invalid numeric rows similarly to `example_solver.py`. Candidate task order should preserve the input `task_id_list` string for output stability.

### Evaluator

`autosolver.evaluator` validates and compares solutions.

Validity checks:

- A courier may appear at most once.
- Selected bundles may repeat or overlap because a task package can be assigned to multiple couriers.
- Selected assignments must refer to known candidates.

Objective comparison:

1. Maximize unique covered task count.
2. Minimize total score.
3. Prefer fewer assignments as a deterministic tie-breaker.
4. Prefer stable lexical output as a final tie-breaker.

This objective matches the current interpretation of the problem statement: accepted order count is primary, score is secondary.

### Strategy Interface

Each strategy implements a common protocol:

```python
class Strategy(Protocol):
    name: str

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Solution | None,
        budget: TimeBudget,
    ) -> Solution:
        ...
```

Strategies must be deterministic unless they receive an explicit seeded random source. They must regularly check the time budget and return the best partial result they have if time is nearly exhausted.

### Initial Strategies

The first scaffold includes:

- `GreedyByScore`: baseline-equivalent strategy that sorts candidates by ascending `total_score`.
- `GreedyByExpectedScore`: sorts by a score/willingness style metric to account for acceptance probability.
- `GreedyByCoverage`: prioritizes candidates that improve coverage, then score.
- `LocalRepair`: starts from the incumbent and tries simple one-for-one or small replacement moves to improve coverage or reduce score.

These strategies are intentionally simple. They provide a working strategy registry and a place to add future ILP, beam search, randomized restarts, or metaheuristics.

### Agentic Loop

`autosolver.solver.AutoSolver` owns the main loop:

1. Parse-ready `ProblemInstance` enters the solver.
2. Create a `TimeBudget`, leaving a small safety margin below the 10 second limit.
3. Ask `StrategySelector` for the next strategy and parameters.
4. Run the strategy.
5. Validate and score the candidate solution.
6. Keep it if it improves the incumbent.
7. Record the attempt.
8. Repeat until the budget is exhausted or the selector has no useful strategy left.
9. Return the incumbent, falling back to an empty valid solution only if all strategies fail.

The first selector is rule-based:

- Run baseline score greedy first.
- Try willingness-aware and coverage-aware variants next.
- If coverage improves, continue nearby variants.
- If coverage stalls, attempt local repair to reduce score.
- Stop early when the remaining budget is too small for another useful attempt.

This gives the project an agentic structure without making the first version depend on an LLM.

## Local Runner

`run_local.py` should support:

```powershell
uv run python run_local.py data/large_seed301.txt
```

It reads the file, calls `solver.solve`, and prints:

```text
task_id_list<TAB>courier_id,courier_id,...
```

matching `example_solver.py`.

## Testing

Initial tests should cover:

- Parser handles headers, empty lines, invalid rows, single-task bundles, and two-task bundles.
- Evaluator allows duplicate or overlapping task packages, and rejects duplicate couriers.
- Objective comparison prioritizes coverage before score.
- `solver.solve` returns the exact expected shape: a list of `(str, list[str])`.
- The baseline strategy can produce a valid solution for `data/large_seed301.txt`.

Tests should run with:

```powershell
uv run python -m pytest
```

If pytest is not yet configured, the scaffold can still include test files and defer dependency setup to a later step.

## Error Handling

- Invalid input rows are skipped during parsing, matching the forgiving behavior of the baseline.
- Strategy exceptions are caught at the `AutoSolver` level and recorded as failed attempts so one bad strategy does not prevent returning a valid incumbent.
- If no candidate solution is available, return an empty solution rather than raising from `solve`.
- The local runner may print errors for file access problems, but the competition entry point should avoid stdout/stderr side effects.

## Extension Points

Future improvements can add:

- Randomized greedy restarts with a fixed seed.
- Beam search over compatible bundles.
- Exact or approximate set-packing formulations.
- Strategy parameter generation from attempt history.
- Optional LLM planner outside the submission path.
- Richer evaluation if the official judge clarifies willingness handling or multi-courier assignment semantics.

## Open Assumptions

- The validity model treats courier uniqueness as the hard assignment constraint. Task packages come from input rows and may be assigned to multiple couriers.
- The solver should not create new task bundles from individual orders; it should only choose among the provided `task_id_list` candidates.
- `willingness` is used by heuristic strategies but is not part of the first objective comparison unless an official scoring function requires it.
- The first submitted entry should remain dependency-light and avoid optional packages unless they clearly improve score under the 10 second limit.
