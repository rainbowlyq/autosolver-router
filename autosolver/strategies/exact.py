from collections import defaultdict
from time import perf_counter
from typing import FrozenSet, NamedTuple, Optional, Tuple

from autosolver.budget import TimeBudget
from autosolver.evaluator import evaluate_solution
from autosolver.models import Assignment, Candidate, ProblemInstance, Solution


class _Option(NamedTuple):
    candidate: Candidate
    task_indexes: Tuple[int, ...]
    acceptance_probability: float
    expected_score: float


class _Metrics(NamedTuple):
    covered_tasks: float
    total_score: float
    assignment_count: int
    signature: Tuple[str, ...]


class ExactBranchAndBound:
    name = "exact_branch_and_bound"

    def __init__(self, max_seconds: float = 0.5, max_budget_fraction: float = 0.1) -> None:
        self.max_seconds = max(0.0, max_seconds)
        self.max_budget_fraction = max(0.0, max_budget_fraction)

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Optional[Solution],
        budget: TimeBudget,
    ) -> Solution:
        started_at = perf_counter()
        allowed_seconds = min(self.max_seconds, budget.remaining * self.max_budget_fraction)

        def expired() -> bool:
            return budget.expired() or perf_counter() - started_at >= allowed_seconds

        if expired():
            return incumbent or Solution.empty()

        groups = _group_options_by_courier(instance)
        suffix_reachable_tasks = _build_suffix_reachable_tasks(groups)
        best_solution = incumbent or Solution.empty()
        best_metrics = _solution_metrics(instance, best_solution)
        initial_miss_probabilities = tuple(1.0 for _ in instance.task_ids)

        def search(
            group_index: int,
            miss_probabilities: Tuple[float, ...],
            covered_tasks: float,
            total_score: float,
            assignments: Tuple[Assignment, ...],
        ) -> None:
            nonlocal best_solution, best_metrics

            if expired():
                return

            candidate_metrics = _state_metrics(covered_tasks, total_score, assignments)
            if _is_better_metrics(candidate_metrics, best_metrics):
                best_solution = Solution(assignments=assignments)
                best_metrics = candidate_metrics

            if group_index >= len(groups):
                return

            upper_bound = _coverage_upper_bound(
                covered_tasks,
                miss_probabilities,
                suffix_reachable_tasks[group_index],
            )
            if round(upper_bound, 12) < best_metrics.covered_tasks:
                return

            for option in groups[group_index]:
                if expired():
                    return
                next_miss_probabilities = list(miss_probabilities)
                next_covered_tasks = covered_tasks
                miss_multiplier = 1.0 - option.acceptance_probability
                for task_index in option.task_indexes:
                    old_miss_probability = next_miss_probabilities[task_index]
                    new_miss_probability = old_miss_probability * miss_multiplier
                    next_miss_probabilities[task_index] = new_miss_probability
                    next_covered_tasks += old_miss_probability - new_miss_probability

                search(
                    group_index + 1,
                    tuple(next_miss_probabilities),
                    next_covered_tasks,
                    total_score + option.expected_score,
                    assignments + (Assignment.from_candidate(option.candidate),),
                )

            search(
                group_index + 1,
                miss_probabilities,
                covered_tasks,
                total_score,
                assignments,
            )

        search(
            group_index=0,
            miss_probabilities=initial_miss_probabilities,
            covered_tasks=0.0,
            total_score=0.0,
            assignments=(),
        )
        return best_solution


def _acceptance_probability(candidate: Candidate) -> float:
    return min(max(candidate.willingness, 0.0), 1.0)


def _group_options_by_courier(instance: ProblemInstance) -> Tuple[Tuple[_Option, ...], ...]:
    task_index_by_id = {
        task_id: task_index
        for task_index, task_id in enumerate(instance.task_ids)
    }
    options_by_courier = defaultdict(list)

    for candidate in instance.candidates:
        acceptance_probability = _acceptance_probability(candidate)
        if acceptance_probability <= 0.0:
            continue
        task_indexes = tuple(task_index_by_id[task_id] for task_id in candidate.task_ids)
        options_by_courier[candidate.courier_id].append(
            _Option(
                candidate=candidate,
                task_indexes=task_indexes,
                acceptance_probability=acceptance_probability,
                expected_score=candidate.total_score * acceptance_probability,
            )
        )

    groups = []
    for courier_id, options in options_by_courier.items():
        ordered_options = tuple(
            sorted(
                options,
                key=lambda option: (
                    -len(option.task_indexes),
                    option.expected_score,
                    option.candidate.task_id_list,
                    option.candidate.courier_id,
                    option.candidate.index,
                ),
            )
        )
        groups.append((courier_id, ordered_options))

    return tuple(
        options
        for _, options in sorted(
            groups,
            key=lambda item: (
                -max(len(option.task_indexes) for option in item[1]),
                -len(item[1]),
                item[0],
            ),
        )
    )


def _build_suffix_reachable_tasks(groups: Tuple[Tuple[_Option, ...], ...]) -> Tuple[FrozenSet[int], ...]:
    suffix = [frozenset() for _ in range(len(groups) + 1)]
    reachable = set()

    for group_index in range(len(groups) - 1, -1, -1):
        for option in groups[group_index]:
            reachable.update(option.task_indexes)
        suffix[group_index] = frozenset(reachable)

    suffix[len(groups)] = frozenset()
    return tuple(suffix)


def _coverage_upper_bound(
    covered_tasks: float,
    miss_probabilities: Tuple[float, ...],
    reachable_tasks: FrozenSet[int],
) -> float:
    return covered_tasks + sum(
        miss_probabilities[task_index]
        for task_index in reachable_tasks
    )


def _solution_metrics(instance: ProblemInstance, solution: Solution) -> _Metrics:
    evaluation = evaluate_solution(instance, solution)
    if not evaluation.valid:
        return _Metrics(
            covered_tasks=float("-inf"),
            total_score=float("inf"),
            assignment_count=len(solution.assignments),
            signature=(),
        )
    return _Metrics(
        covered_tasks=evaluation.expected_covered_tasks,
        total_score=evaluation.expected_total_score,
        assignment_count=evaluation.assignment_count,
        signature=evaluation.signature,
    )


def _state_metrics(
    covered_tasks: float,
    total_score: float,
    assignments: Tuple[Assignment, ...],
) -> _Metrics:
    return _Metrics(
        covered_tasks=round(covered_tasks, 12),
        total_score=round(total_score, 12),
        assignment_count=len(assignments),
        signature=tuple(
            sorted(
                f"{assignment.task_id_list}\t{','.join(assignment.courier_ids)}"
                for assignment in assignments
            )
        ),
    )


def _is_better_metrics(candidate: _Metrics, incumbent: _Metrics) -> bool:
    if candidate.covered_tasks != incumbent.covered_tasks:
        return candidate.covered_tasks > incumbent.covered_tasks
    if candidate.total_score != incumbent.total_score:
        return candidate.total_score < incumbent.total_score
    if candidate.assignment_count != incumbent.assignment_count:
        return candidate.assignment_count < incumbent.assignment_count
    return candidate.signature < incumbent.signature
