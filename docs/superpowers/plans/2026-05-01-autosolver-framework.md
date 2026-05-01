# AutoSolver Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a submission-compatible AutoSolver scaffold with modular parsing, evaluation, strategy execution, and local running.

**Architecture:** Keep `solver.py` as the competition entry point and put reusable logic under `autosolver/`. The core solver runs a time-budgeted loop over registered strategies, evaluates each attempt, and returns the best valid solution in the same shape as `example_solver.py`.

**Tech Stack:** Python 3.13 standard library, `dataclasses`, `typing`, `time.perf_counter`, `unittest`-compatible tests runnable through `pytest` when available, and `uv run` for local commands.

---

## File Structure

- Create `autosolver/__init__.py`: package exports.
- Create `autosolver/models.py`: immutable core data structures.
- Create `autosolver/parser.py`: TSV input parsing and output formatting.
- Create `autosolver/evaluator.py`: validity checks and objective comparison.
- Create `autosolver/budget.py`: time budget helper.
- Create `autosolver/selector.py`: rule-based strategy selector.
- Create `autosolver/solver.py`: `AutoSolver` orchestration loop.
- Create `autosolver/strategies/__init__.py`: strategy exports.
- Create `autosolver/strategies/base.py`: strategy protocol.
- Create `autosolver/strategies/greedy.py`: baseline-equivalent greedy strategy and shared greedy builder.
- Create `autosolver/strategies/greedy_variants.py`: willingness-aware and coverage-aware greedy variants.
- Create `autosolver/strategies/local_search.py`: incumbent repair strategy.
- Create `solver.py`: competition-compatible `solve(input_text: str) -> list`.
- Create `run_local.py`: local file runner.
- Create `tests/test_models.py`: data model tests.
- Create `tests/test_parser.py`: parser and formatter tests.
- Create `tests/test_evaluator.py`: evaluator tests.
- Create `tests/test_strategies.py`: strategy behavior tests.
- Create `tests/test_autosolver.py`: main loop tests.
- Create `tests/test_solver_contract.py`: top-level entry point tests.

---

### Task 1: Package Scaffolding And Models

**Files:**
- Create: `autosolver/__init__.py`
- Create: `autosolver/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing model tests**

Create `tests/test_models.py`:

```python
import unittest

from autosolver.models import Assignment, Candidate, ProblemInstance, Solution


class ModelTests(unittest.TestCase):
    def test_problem_instance_derives_sorted_task_and_courier_ids(self):
        candidates = (
            Candidate(
                index=0,
                task_id_list="T0002,T0001",
                task_ids=("T0002", "T0001"),
                courier_id="C002",
                total_score=12.5,
                willingness=0.4,
            ),
            Candidate(
                index=1,
                task_id_list="T0003",
                task_ids=("T0003",),
                courier_id="C001",
                total_score=7.0,
                willingness=0.9,
            ),
        )

        instance = ProblemInstance.from_candidates(candidates)

        self.assertEqual(instance.task_ids, ("T0001", "T0002", "T0003"))
        self.assertEqual(instance.courier_ids, ("C001", "C002"))

    def test_assignment_from_candidate_uses_candidate_courier(self):
        candidate = Candidate(
            index=3,
            task_id_list="T0004",
            task_ids=("T0004",),
            courier_id="C007",
            total_score=3.25,
            willingness=0.75,
        )

        assignment = Assignment.from_candidate(candidate)

        self.assertEqual(assignment.task_id_list, "T0004")
        self.assertEqual(assignment.task_ids, ("T0004",))
        self.assertEqual(assignment.courier_ids, ("C007",))
        self.assertEqual(assignment.total_score, 3.25)

    def test_solution_empty_is_valid_shape(self):
        solution = Solution.empty()

        self.assertEqual(solution.assignments, ())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run model tests to verify they fail**

Run:

```powershell
uv run python -m unittest tests.test_models -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'autosolver'`.

- [ ] **Step 3: Create package exports**

Create `autosolver/__init__.py`:

```python
"""AutoSolver framework package."""

from autosolver.models import Assignment, Candidate, ProblemInstance, Solution

__all__ = ["Assignment", "Candidate", "ProblemInstance", "Solution"]
```

- [ ] **Step 4: Create model implementation**

Create `autosolver/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Candidate:
    index: int
    task_id_list: str
    task_ids: tuple[str, ...]
    courier_id: str
    total_score: float
    willingness: float


@dataclass(frozen=True, slots=True)
class ProblemInstance:
    candidates: tuple[Candidate, ...]
    task_ids: tuple[str, ...] = field(default_factory=tuple)
    courier_ids: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_candidates(cls, candidates: tuple[Candidate, ...]) -> "ProblemInstance":
        task_ids = sorted({task_id for candidate in candidates for task_id in candidate.task_ids})
        courier_ids = sorted({candidate.courier_id for candidate in candidates})
        return cls(
            candidates=tuple(candidates),
            task_ids=tuple(task_ids),
            courier_ids=tuple(courier_ids),
        )


@dataclass(frozen=True, slots=True)
class Assignment:
    candidate: Candidate
    courier_ids: tuple[str, ...]

    @classmethod
    def from_candidate(cls, candidate: Candidate) -> "Assignment":
        return cls(candidate=candidate, courier_ids=(candidate.courier_id,))

    @property
    def task_id_list(self) -> str:
        return self.candidate.task_id_list

    @property
    def task_ids(self) -> tuple[str, ...]:
        return self.candidate.task_ids

    @property
    def total_score(self) -> float:
        return self.candidate.total_score


@dataclass(frozen=True, slots=True)
class Solution:
    assignments: tuple[Assignment, ...]

    @classmethod
    def empty(cls) -> "Solution":
        return cls(assignments=())


@dataclass(frozen=True, slots=True)
class AttemptRecord:
    strategy_name: str
    elapsed_seconds: float
    valid: bool
    improved: bool
    covered_tasks: int
    total_score: float
    error: str = ""
```

- [ ] **Step 5: Run model tests to verify they pass**

Run:

```powershell
uv run python -m unittest tests.test_models -v
```

Expected: PASS, 3 tests.

- [ ] **Step 6: Commit model scaffold**

Run:

```powershell
git add autosolver/__init__.py autosolver/models.py tests/test_models.py
git commit -m "feat: add autosolver core models"
```

---

### Task 2: Parser And Output Formatting

**Files:**
- Create: `autosolver/parser.py`
- Create: `tests/test_parser.py`

- [ ] **Step 1: Write the failing parser tests**

Create `tests/test_parser.py`:

```python
import unittest

from autosolver.models import Assignment, Solution
from autosolver.parser import format_output_rows, parse_problem, solution_to_output


class ParserTests(unittest.TestCase):
    def test_parse_problem_skips_header_empty_lines_and_invalid_rows(self):
        input_text = "\n".join(
            [
                "task_id_list\tcourier_id\ttotal_score\twillingness",
                "T0001,T0002\tC001\t12.5\t0.8",
                "",
                "bad\trow",
                "T0003\tC002\tnot-a-number\t0.3",
                "T0004\tC003\t8.25\t0.6",
            ]
        )

        instance = parse_problem(input_text)

        self.assertEqual(len(instance.candidates), 2)
        self.assertEqual(instance.candidates[0].task_id_list, "T0001,T0002")
        self.assertEqual(instance.candidates[0].task_ids, ("T0001", "T0002"))
        self.assertEqual(instance.candidates[0].courier_id, "C001")
        self.assertEqual(instance.candidates[0].total_score, 12.5)
        self.assertEqual(instance.candidates[0].willingness, 0.8)
        self.assertEqual(instance.candidates[1].index, 4)

    def test_solution_to_output_matches_competition_shape(self):
        instance = parse_problem(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001\tC001\t4.0\t0.7",
                ]
            )
        )
        solution = Solution(assignments=(Assignment.from_candidate(instance.candidates[0]),))

        output = solution_to_output(solution)

        self.assertEqual(output, [("T0001", ["C001"])])

    def test_format_output_rows_matches_example_solver_printing(self):
        text = format_output_rows([("T0001,T0002", ["C001"]), ("T0003", ["C002", "C003"])])

        self.assertEqual(text, "T0001,T0002\tC001\nT0003\tC002,C003")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run parser tests to verify they fail**

Run:

```powershell
uv run python -m unittest tests.test_parser -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'autosolver.parser'`.

- [ ] **Step 3: Create parser implementation**

Create `autosolver/parser.py`:

```python
from __future__ import annotations

from autosolver.models import Candidate, ProblemInstance, Solution


def parse_problem(input_text: str) -> ProblemInstance:
    lines = input_text.strip().splitlines()
    start = 1 if lines and lines[0].startswith("task_id_list") else 0
    candidates: list[Candidate] = []

    for row_index, raw_line in enumerate(lines[start:], start=start):
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split("\t")
        if len(parts) < 4:
            continue

        task_id_list, courier_id, score_text, willingness_text = parts[:4]
        try:
            total_score = float(score_text)
            willingness = float(willingness_text)
        except ValueError:
            continue

        task_ids = tuple(task_id.strip() for task_id in task_id_list.split(",") if task_id.strip())
        if not task_ids:
            continue

        candidates.append(
            Candidate(
                index=row_index,
                task_id_list=task_id_list.strip(),
                task_ids=task_ids,
                courier_id=courier_id.strip(),
                total_score=total_score,
                willingness=willingness,
            )
        )

    return ProblemInstance.from_candidates(tuple(candidates))


def solution_to_output(solution: Solution) -> list[tuple[str, list[str]]]:
    return [
        (assignment.task_id_list, list(assignment.courier_ids))
        for assignment in solution.assignments
    ]


def format_output_rows(output: list[tuple[str, list[str]]]) -> str:
    return "\n".join(
        f"{task_id_list}\t{','.join(courier_ids)}"
        for task_id_list, courier_ids in output
    )
```

- [ ] **Step 4: Run parser tests to verify they pass**

Run:

```powershell
uv run python -m unittest tests.test_parser -v
```

Expected: PASS, 3 tests.

- [ ] **Step 5: Commit parser**

Run:

```powershell
git add autosolver/parser.py tests/test_parser.py
git commit -m "feat: add autosolver parser"
```

---

### Task 3: Evaluator And Objective Comparison

**Files:**
- Create: `autosolver/evaluator.py`
- Create: `tests/test_evaluator.py`

- [ ] **Step 1: Write the failing evaluator tests**

Create `tests/test_evaluator.py`:

```python
import unittest

from autosolver.evaluator import evaluate_solution, is_better_solution
from autosolver.models import Assignment, Solution
from autosolver.parser import parse_problem


def make_instance():
    return parse_problem(
        "\n".join(
            [
                "task_id_list\tcourier_id\ttotal_score\twillingness",
                "T0001\tC001\t10.0\t0.5",
                "T0002\tC002\t12.0\t0.5",
                "T0001,T0002\tC003\t30.0\t0.5",
                "T0003\tC001\t1.0\t0.5",
            ]
        )
    )


class EvaluatorTests(unittest.TestCase):
    def test_evaluate_solution_counts_covered_tasks_and_score(self):
        instance = make_instance()
        solution = Solution(
            assignments=(
                Assignment.from_candidate(instance.candidates[0]),
                Assignment.from_candidate(instance.candidates[1]),
            )
        )

        evaluation = evaluate_solution(instance, solution)

        self.assertTrue(evaluation.valid)
        self.assertEqual(evaluation.covered_tasks, 2)
        self.assertEqual(evaluation.total_score, 22.0)
        self.assertEqual(evaluation.assignment_count, 2)

    def test_evaluate_solution_rejects_duplicate_tasks(self):
        instance = make_instance()
        solution = Solution(
            assignments=(
                Assignment.from_candidate(instance.candidates[0]),
                Assignment.from_candidate(instance.candidates[2]),
            )
        )

        evaluation = evaluate_solution(instance, solution)

        self.assertFalse(evaluation.valid)
        self.assertIn("duplicate task T0001", evaluation.errors)

    def test_evaluate_solution_rejects_duplicate_couriers(self):
        instance = make_instance()
        solution = Solution(
            assignments=(
                Assignment.from_candidate(instance.candidates[0]),
                Assignment.from_candidate(instance.candidates[3]),
            )
        )

        evaluation = evaluate_solution(instance, solution)

        self.assertFalse(evaluation.valid)
        self.assertIn("duplicate courier C001", evaluation.errors)

    def test_is_better_prioritizes_coverage_before_score(self):
        instance = make_instance()
        incumbent = Solution(assignments=(Assignment.from_candidate(instance.candidates[0]),))
        candidate = Solution(assignments=(Assignment.from_candidate(instance.candidates[2]),))

        self.assertTrue(is_better_solution(instance, candidate, incumbent))

    def test_is_better_uses_lower_score_when_coverage_ties(self):
        instance = make_instance()
        incumbent = Solution(assignments=(Assignment.from_candidate(instance.candidates[2]),))
        candidate = Solution(
            assignments=(
                Assignment.from_candidate(instance.candidates[0]),
                Assignment.from_candidate(instance.candidates[1]),
            )
        )

        self.assertTrue(is_better_solution(instance, candidate, incumbent))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run evaluator tests to verify they fail**

Run:

```powershell
uv run python -m unittest tests.test_evaluator -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'autosolver.evaluator'`.

- [ ] **Step 3: Create evaluator implementation**

Create `autosolver/evaluator.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from autosolver.models import ProblemInstance, Solution


@dataclass(frozen=True, slots=True)
class Evaluation:
    valid: bool
    covered_tasks: int
    total_score: float
    assignment_count: int
    signature: tuple[str, ...]
    errors: tuple[str, ...] = ()


def evaluate_solution(instance: ProblemInstance, solution: Solution) -> Evaluation:
    known_candidate_indexes = {candidate.index for candidate in instance.candidates}
    used_tasks: set[str] = set()
    used_couriers: set[str] = set()
    errors: list[str] = []
    total_score = 0.0
    signature: list[str] = []

    for assignment in solution.assignments:
        candidate = assignment.candidate
        if candidate.index not in known_candidate_indexes:
            errors.append(f"unknown candidate index {candidate.index}")

        total_score += candidate.total_score
        signature.append(f"{candidate.task_id_list}\t{','.join(assignment.courier_ids)}")

        for task_id in candidate.task_ids:
            if task_id in used_tasks:
                errors.append(f"duplicate task {task_id}")
            used_tasks.add(task_id)

        for courier_id in assignment.courier_ids:
            if courier_id in used_couriers:
                errors.append(f"duplicate courier {courier_id}")
            used_couriers.add(courier_id)

    return Evaluation(
        valid=not errors,
        covered_tasks=len(used_tasks),
        total_score=round(total_score, 12),
        assignment_count=len(solution.assignments),
        signature=tuple(sorted(signature)),
        errors=tuple(errors),
    )


def is_better_solution(
    instance: ProblemInstance,
    candidate: Solution,
    incumbent: Solution | None,
) -> bool:
    candidate_eval = evaluate_solution(instance, candidate)
    if not candidate_eval.valid:
        return False

    if incumbent is None:
        return True

    incumbent_eval = evaluate_solution(instance, incumbent)
    if not incumbent_eval.valid:
        return True

    if candidate_eval.covered_tasks != incumbent_eval.covered_tasks:
        return candidate_eval.covered_tasks > incumbent_eval.covered_tasks

    if candidate_eval.total_score != incumbent_eval.total_score:
        return candidate_eval.total_score < incumbent_eval.total_score

    if candidate_eval.assignment_count != incumbent_eval.assignment_count:
        return candidate_eval.assignment_count < incumbent_eval.assignment_count

    return candidate_eval.signature < incumbent_eval.signature
```

- [ ] **Step 4: Run evaluator tests to verify they pass**

Run:

```powershell
uv run python -m unittest tests.test_evaluator -v
```

Expected: PASS, 5 tests.

- [ ] **Step 5: Commit evaluator**

Run:

```powershell
git add autosolver/evaluator.py tests/test_evaluator.py
git commit -m "feat: add autosolver evaluator"
```

---

### Task 4: Greedy Strategies And Local Repair

**Files:**
- Create: `autosolver/strategies/__init__.py`
- Create: `autosolver/strategies/base.py`
- Create: `autosolver/strategies/greedy.py`
- Create: `autosolver/strategies/greedy_variants.py`
- Create: `autosolver/strategies/local_search.py`
- Create: `tests/test_strategies.py`

- [ ] **Step 1: Write the failing strategy tests**

Create `tests/test_strategies.py`:

```python
import unittest

from autosolver.budget import TimeBudget
from autosolver.evaluator import evaluate_solution
from autosolver.parser import parse_problem
from autosolver.strategies import (
    GreedyByCoverage,
    GreedyByExpectedScore,
    GreedyByScore,
    LocalRepair,
)


class StrategyTests(unittest.TestCase):
    def test_greedy_by_score_matches_baseline_choice_order(self):
        instance = parse_problem(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001\tC001\t20.0\t0.5",
                    "T0001,T0002\tC002\t5.0\t0.5",
                    "T0003\tC001\t1.0\t0.5",
                ]
            )
        )

        solution = GreedyByScore().run(instance, None, TimeBudget(1.0))

        self.assertEqual(
            [(assignment.task_id_list, assignment.courier_ids) for assignment in solution.assignments],
            [("T0003", ("C001",)), ("T0001,T0002", ("C002",))],
        )

    def test_greedy_variants_return_valid_solutions(self):
        instance = parse_problem(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001\tC001\t10.0\t0.9",
                    "T0002\tC002\t9.0\t0.1",
                    "T0001,T0002\tC003\t15.0\t0.8",
                ]
            )
        )

        for strategy in (GreedyByExpectedScore(), GreedyByCoverage()):
            with self.subTest(strategy=strategy.name):
                solution = strategy.run(instance, None, TimeBudget(1.0))
                evaluation = evaluate_solution(instance, solution)
                self.assertTrue(evaluation.valid)
                self.assertGreaterEqual(evaluation.covered_tasks, 1)

    def test_local_repair_keeps_or_improves_valid_incumbent(self):
        instance = parse_problem(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001\tC001\t10.0\t0.5",
                    "T0002\tC002\t10.0\t0.5",
                    "T0001,T0002\tC003\t15.0\t0.5",
                ]
            )
        )
        incumbent = GreedyByScore().run(instance, None, TimeBudget(1.0))

        repaired = LocalRepair().run(instance, incumbent, TimeBudget(1.0))

        self.assertTrue(evaluate_solution(instance, repaired).valid)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run strategy tests to verify they fail**

Run:

```powershell
uv run python -m unittest tests.test_strategies -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'autosolver.budget'`.

- [ ] **Step 3: Create strategy protocol**

Create `autosolver/strategies/base.py`:

```python
from __future__ import annotations

from typing import Protocol

from autosolver.budget import TimeBudget
from autosolver.models import ProblemInstance, Solution


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

- [ ] **Step 4: Create temporary time budget helper needed by strategies**

Create `autosolver/budget.py`:

```python
from __future__ import annotations

from time import perf_counter


class TimeBudget:
    def __init__(self, limit_seconds: float, safety_margin_seconds: float = 0.05) -> None:
        self.limit_seconds = max(0.0, limit_seconds)
        self.safety_margin_seconds = max(0.0, safety_margin_seconds)
        self.started_at = perf_counter()

    @property
    def elapsed(self) -> float:
        return perf_counter() - self.started_at

    @property
    def remaining(self) -> float:
        return max(0.0, self.limit_seconds - self.elapsed)

    def expired(self) -> bool:
        return self.remaining <= self.safety_margin_seconds

    def has_time_for(self, seconds: float) -> bool:
        return self.remaining > seconds + self.safety_margin_seconds
```

- [ ] **Step 5: Create baseline greedy implementation**

Create `autosolver/strategies/greedy.py`:

```python
from __future__ import annotations

from collections.abc import Callable, Iterable

from autosolver.budget import TimeBudget
from autosolver.models import Assignment, Candidate, ProblemInstance, Solution

CandidateKey = Callable[[Candidate], tuple]


def build_greedy_solution(
    instance: ProblemInstance,
    ordered_candidates: Iterable[Candidate],
    budget: TimeBudget,
) -> Solution:
    used_tasks: set[str] = set()
    used_couriers: set[str] = set()
    assignments: list[Assignment] = []

    for candidate in ordered_candidates:
        if budget.expired():
            break
        if candidate.courier_id in used_couriers:
            continue
        if any(task_id in used_tasks for task_id in candidate.task_ids):
            continue

        assignments.append(Assignment.from_candidate(candidate))
        used_couriers.add(candidate.courier_id)
        used_tasks.update(candidate.task_ids)

    return Solution(assignments=tuple(assignments))


class GreedyByScore:
    name = "greedy_by_score"

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Solution | None,
        budget: TimeBudget,
    ) -> Solution:
        ordered = sorted(
            instance.candidates,
            key=lambda candidate: (
                candidate.total_score,
                len(candidate.task_ids),
                candidate.task_id_list,
                candidate.courier_id,
                candidate.index,
            ),
        )
        return build_greedy_solution(instance, ordered, budget)
```

- [ ] **Step 6: Create greedy variants**

Create `autosolver/strategies/greedy_variants.py`:

```python
from __future__ import annotations

from autosolver.budget import TimeBudget
from autosolver.models import Candidate, ProblemInstance, Solution
from autosolver.strategies.greedy import build_greedy_solution


def _safe_willingness(candidate: Candidate) -> float:
    return max(candidate.willingness, 0.01)


class GreedyByExpectedScore:
    name = "greedy_by_expected_score"

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Solution | None,
        budget: TimeBudget,
    ) -> Solution:
        ordered = sorted(
            instance.candidates,
            key=lambda candidate: (
                candidate.total_score / _safe_willingness(candidate),
                candidate.total_score,
                candidate.task_id_list,
                candidate.courier_id,
                candidate.index,
            ),
        )
        return build_greedy_solution(instance, ordered, budget)


class GreedyByCoverage:
    name = "greedy_by_coverage"

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Solution | None,
        budget: TimeBudget,
    ) -> Solution:
        ordered = sorted(
            instance.candidates,
            key=lambda candidate: (
                -len(candidate.task_ids),
                candidate.total_score / len(candidate.task_ids),
                candidate.total_score,
                candidate.task_id_list,
                candidate.courier_id,
                candidate.index,
            ),
        )
        return build_greedy_solution(instance, ordered, budget)
```

- [ ] **Step 7: Create local repair strategy**

Create `autosolver/strategies/local_search.py`:

```python
from __future__ import annotations

from autosolver.budget import TimeBudget
from autosolver.evaluator import is_better_solution
from autosolver.models import Assignment, ProblemInstance, Solution
from autosolver.strategies.greedy import GreedyByScore


class LocalRepair:
    name = "local_repair"

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Solution | None,
        budget: TimeBudget,
    ) -> Solution:
        best = incumbent if incumbent is not None else GreedyByScore().run(instance, None, budget)
        if best is None:
            return Solution.empty()

        improved = True
        while improved and not budget.expired():
            improved = False
            replacement = self._best_single_replacement(instance, best, budget)
            if replacement is not None and is_better_solution(instance, replacement, best):
                best = replacement
                improved = True

        return best

    def _best_single_replacement(
        self,
        instance: ProblemInstance,
        incumbent: Solution,
        budget: TimeBudget,
    ) -> Solution | None:
        best_candidate_solution: Solution | None = None
        assignments = list(incumbent.assignments)

        for remove_index in range(len(assignments)):
            if budget.expired():
                break

            kept = assignments[:remove_index] + assignments[remove_index + 1 :]
            kept_tasks = {task_id for assignment in kept for task_id in assignment.task_ids}
            kept_couriers = {courier_id for assignment in kept for courier_id in assignment.courier_ids}

            for candidate in instance.candidates:
                if budget.expired():
                    break
                if candidate.courier_id in kept_couriers:
                    continue
                if any(task_id in kept_tasks for task_id in candidate.task_ids):
                    continue

                trial = Solution(assignments=tuple(kept + [Assignment.from_candidate(candidate)]))
                if is_better_solution(instance, trial, incumbent):
                    if best_candidate_solution is None or is_better_solution(
                        instance,
                        trial,
                        best_candidate_solution,
                    ):
                        best_candidate_solution = trial

        return best_candidate_solution
```

- [ ] **Step 8: Create strategy exports**

Create `autosolver/strategies/__init__.py`:

```python
from autosolver.strategies.base import Strategy
from autosolver.strategies.greedy import GreedyByScore
from autosolver.strategies.greedy_variants import GreedyByCoverage, GreedyByExpectedScore
from autosolver.strategies.local_search import LocalRepair

__all__ = [
    "GreedyByCoverage",
    "GreedyByExpectedScore",
    "GreedyByScore",
    "LocalRepair",
    "Strategy",
]
```

- [ ] **Step 9: Run strategy tests to verify they pass**

Run:

```powershell
uv run python -m unittest tests.test_strategies -v
```

Expected: PASS, 3 tests.

- [ ] **Step 10: Commit strategies**

Run:

```powershell
git add autosolver/budget.py autosolver/strategies tests/test_strategies.py
git commit -m "feat: add initial autosolver strategies"
```

---

### Task 5: Strategy Selector And AutoSolver Loop

**Files:**
- Create: `autosolver/selector.py`
- Create: `autosolver/solver.py`
- Create: `tests/test_autosolver.py`
- Modify: `autosolver/__init__.py`

- [ ] **Step 1: Write the failing AutoSolver tests**

Create `tests/test_autosolver.py`:

```python
import unittest

from autosolver.evaluator import evaluate_solution
from autosolver.parser import parse_problem
from autosolver.solver import AutoSolver


class AutoSolverTests(unittest.TestCase):
    def test_autosolver_returns_valid_solution_and_records_attempts(self):
        instance = parse_problem(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001\tC001\t10.0\t0.5",
                    "T0002\tC002\t11.0\t0.5",
                    "T0001,T0002\tC003\t15.0\t0.9",
                ]
            )
        )
        solver = AutoSolver(time_limit_seconds=1.0)

        solution = solver.solve(instance)

        evaluation = evaluate_solution(instance, solution)
        self.assertTrue(evaluation.valid)
        self.assertEqual(evaluation.covered_tasks, 2)
        self.assertGreaterEqual(len(solver.history), 1)

    def test_autosolver_empty_input_returns_empty_solution(self):
        instance = parse_problem("task_id_list\tcourier_id\ttotal_score\twillingness\n")
        solver = AutoSolver(time_limit_seconds=1.0)

        solution = solver.solve(instance)

        self.assertEqual(solution.assignments, ())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run AutoSolver tests to verify they fail**

Run:

```powershell
uv run python -m unittest tests.test_autosolver -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'autosolver.solver'`.

- [ ] **Step 3: Create strategy selector**

Create `autosolver/selector.py`:

```python
from __future__ import annotations

from autosolver.budget import TimeBudget
from autosolver.models import AttemptRecord
from autosolver.strategies import (
    GreedyByCoverage,
    GreedyByExpectedScore,
    GreedyByScore,
    LocalRepair,
    Strategy,
)


class StrategySelector:
    def __init__(self, strategies: tuple[Strategy, ...] | None = None) -> None:
        self._strategies = strategies or (
            GreedyByScore(),
            GreedyByExpectedScore(),
            GreedyByCoverage(),
            LocalRepair(),
        )

    def next_strategy(
        self,
        history: tuple[AttemptRecord, ...],
        budget: TimeBudget,
    ) -> Strategy | None:
        if budget.expired():
            return None
        if len(history) >= len(self._strategies):
            return None
        return self._strategies[len(history)]
```

- [ ] **Step 4: Create AutoSolver loop**

Create `autosolver/solver.py`:

```python
from __future__ import annotations

from time import perf_counter

from autosolver.budget import TimeBudget
from autosolver.evaluator import evaluate_solution, is_better_solution
from autosolver.models import AttemptRecord, ProblemInstance, Solution
from autosolver.selector import StrategySelector


class AutoSolver:
    def __init__(
        self,
        time_limit_seconds: float = 9.5,
        selector: StrategySelector | None = None,
    ) -> None:
        self.time_limit_seconds = time_limit_seconds
        self.selector = selector or StrategySelector()
        self.history: list[AttemptRecord] = []

    def solve(self, instance: ProblemInstance) -> Solution:
        if not instance.candidates:
            return Solution.empty()

        budget = TimeBudget(self.time_limit_seconds)
        incumbent: Solution | None = None

        while not budget.expired():
            strategy = self.selector.next_strategy(tuple(self.history), budget)
            if strategy is None:
                break

            started_at = perf_counter()
            try:
                candidate = strategy.run(instance, incumbent, budget)
                evaluation = evaluate_solution(instance, candidate)
                improved = is_better_solution(instance, candidate, incumbent)
                if improved:
                    incumbent = candidate
                self.history.append(
                    AttemptRecord(
                        strategy_name=strategy.name,
                        elapsed_seconds=perf_counter() - started_at,
                        valid=evaluation.valid,
                        improved=improved,
                        covered_tasks=evaluation.covered_tasks,
                        total_score=evaluation.total_score,
                    )
                )
            except Exception as exc:
                self.history.append(
                    AttemptRecord(
                        strategy_name=strategy.name,
                        elapsed_seconds=perf_counter() - started_at,
                        valid=False,
                        improved=False,
                        covered_tasks=0,
                        total_score=float("inf"),
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )

        return incumbent or Solution.empty()
```

- [ ] **Step 5: Update package exports**

Modify `autosolver/__init__.py`:

```python
"""AutoSolver framework package."""

from autosolver.models import Assignment, Candidate, ProblemInstance, Solution
from autosolver.solver import AutoSolver

__all__ = ["Assignment", "AutoSolver", "Candidate", "ProblemInstance", "Solution"]
```

- [ ] **Step 6: Run AutoSolver tests to verify they pass**

Run:

```powershell
uv run python -m unittest tests.test_autosolver -v
```

Expected: PASS, 2 tests.

- [ ] **Step 7: Commit AutoSolver loop**

Run:

```powershell
git add autosolver/__init__.py autosolver/selector.py autosolver/solver.py tests/test_autosolver.py
git commit -m "feat: add autosolver orchestration loop"
```

---

### Task 6: Competition Entry Point And Local Runner

**Files:**
- Create: `solver.py`
- Create: `run_local.py`
- Create: `tests/test_solver_contract.py`

- [ ] **Step 1: Write the failing entry point tests**

Create `tests/test_solver_contract.py`:

```python
import unittest

from solver import solve


class SolverContractTests(unittest.TestCase):
    def test_solve_returns_example_solver_shape(self):
        output = solve(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001\tC001\t10.0\t0.5",
                    "T0002\tC002\t11.0\t0.5",
                ]
            )
        )

        self.assertIsInstance(output, list)
        self.assertEqual(output, [("T0001", ["C001"]), ("T0002", ["C002"])])

    def test_solve_handles_empty_input(self):
        self.assertEqual(solve(""), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run entry point tests to verify they fail**

Run:

```powershell
uv run python -m unittest tests.test_solver_contract -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'solver'`.

- [ ] **Step 3: Create competition entry point**

Create `solver.py`:

```python
from __future__ import annotations

from autosolver.parser import parse_problem, solution_to_output
from autosolver.solver import AutoSolver


def solve(input_text: str) -> list:
    instance = parse_problem(input_text)
    solution = AutoSolver(time_limit_seconds=9.5).solve(instance)
    return solution_to_output(solution)
```

- [ ] **Step 4: Create local runner**

Create `run_local.py`:

```python
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
```

- [ ] **Step 5: Run entry point tests to verify they pass**

Run:

```powershell
uv run python -m unittest tests.test_solver_contract -v
```

Expected: PASS, 2 tests.

- [ ] **Step 6: Run local runner on the large case**

Run:

```powershell
uv run python run_local.py data/large_seed301.txt
```

Expected: prints one assignment per line in `task_id_list<TAB>courier_id[,courier_id...]` format and exits with code 0.

- [ ] **Step 7: Commit entry point and runner**

Run:

```powershell
git add solver.py run_local.py tests/test_solver_contract.py
git commit -m "feat: add competition solver entry point"
```

---

### Task 7: Full Verification

**Files:**
- No new files.

- [ ] **Step 1: Run the full unittest suite**

Run:

```powershell
uv run python -m unittest discover -s tests -v
```

Expected: PASS for all tests.

- [ ] **Step 2: Run pytest if it is installed**

Run:

```powershell
uv run python -m pytest
```

Expected: PASS if pytest is available. If pytest is missing, use the unittest result from Step 1 as the scaffold verification evidence.

- [ ] **Step 3: Run a large-case smoke command and inspect the first rows**

Run:

```powershell
uv run python run_local.py data/large_seed301.txt | Select-Object -First 10
```

Expected: prints 10 output rows or fewer if the solver returns fewer assignments. Each row contains one tab separator.

- [ ] **Step 4: Check git status**

Run:

```powershell
git status --short
```

Expected: no uncommitted framework files after the task commits.

---

## Plan Self-Review

- Spec coverage: Tasks 1-6 cover models, parser, evaluator, strategies, selector, agentic loop, top-level `solve`, and local runner. Task 7 covers verification.
- Scope: The plan builds one cohesive framework and avoids external solvers, LLM calls, experiment storage, and optional reporting.
- Type consistency: `Candidate`, `Assignment`, `Solution`, `ProblemInstance`, `AttemptRecord`, `TimeBudget`, `StrategySelector`, and `AutoSolver` are named consistently across tests and implementation steps.
- Test approach: Tests are standard-library `unittest` tests, so they run without adding dependencies and remain compatible with pytest when pytest is available.
