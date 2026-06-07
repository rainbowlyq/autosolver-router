from collections import defaultdict
from time import perf_counter
from typing import FrozenSet, Optional, Tuple

from autosolver.budget import TimeBudget
from autosolver.evaluator import PENALTY_SCORE, candidate_assignment_cost, evaluate_solution
from autosolver.models import Assignment, Candidate, ProblemInstance, Solution


class _Option:
    __slots__ = ("candidate", "task_indexes", "acceptance_probability", "assignment_cost")

    def __init__(
        self,
        candidate: Candidate,
        task_indexes: Tuple[int, ...],
        acceptance_probability: float,
        assignment_cost: float,
    ) -> None:
        self.candidate = candidate
        self.task_indexes = task_indexes
        self.acceptance_probability = acceptance_probability
        self.assignment_cost = assignment_cost


class _Metrics:
    __slots__ = ("covered_tasks", "total_score", "assignment_count", "signature")

    def __init__(
        self,
        covered_tasks: float,
        total_score: float,
        assignment_count: int,
        signature: Tuple[str, ...],
    ) -> None:
        self.covered_tasks = covered_tasks
        self.total_score = total_score
        self.assignment_count = assignment_count
        self.signature = signature


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
        if incumbent is not None and len(instance.courier_ids) <= 25:
            incumbent_evaluation = evaluate_solution(instance, incumbent)
            all_assignments_are_locally_useful = all(
                candidate_assignment_cost(assignment.candidate)
                <= PENALTY_SCORE * len(assignment.task_ids)
                for assignment in incumbent.assignments
            )
            if (
                incumbent_evaluation.valid
                and incumbent_evaluation.unassigned_count == 0
                and all_assignments_are_locally_useful
            ):
                return incumbent

        groups = _group_options_by_courier(instance)
        best_solution = incumbent or Solution.empty()
        best_metrics = _solution_metrics(instance, best_solution)
        initial_miss_probabilities = tuple(1.0 for _ in instance.task_ids)

        def search(
            group_index: int,
            miss_probabilities: Tuple[float, ...],
            covered_tasks: float,
            assignment_cost: float,
            assigned_task_indexes: FrozenSet[int],
            assignments: Tuple[Assignment, ...],
        ) -> None:
            nonlocal best_solution, best_metrics

            if expired():
                return

            candidate_metrics = _state_metrics(
                covered_tasks,
                assignment_cost,
                assigned_task_indexes,
                assignments,
                len(instance.task_ids),
            )
            if _is_better_metrics(candidate_metrics, best_metrics):
                best_solution = Solution(assignments=assignments)
                best_metrics = candidate_metrics

            if group_index >= len(groups):
                return

            for option in groups[group_index]:
                if expired():
                    return
                if any(task_index in assigned_task_indexes for task_index in option.task_indexes):
                    continue
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
                    assignment_cost + option.assignment_cost,
                    assigned_task_indexes.union(option.task_indexes),
                    assignments + (Assignment.from_candidate(option.candidate),),
                )

            search(
                group_index + 1,
                miss_probabilities,
                covered_tasks,
                assignment_cost,
                assigned_task_indexes,
                assignments,
            )

        search(
            group_index=0,
            miss_probabilities=initial_miss_probabilities,
            covered_tasks=0.0,
            assignment_cost=0.0,
            assigned_task_indexes=frozenset(),
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
        task_indexes = tuple(task_index_by_id[task_id] for task_id in candidate.task_ids)
        options_by_courier[candidate.courier_id].append(
            _Option(
                candidate=candidate,
                task_indexes=task_indexes,
                acceptance_probability=acceptance_probability,
                assignment_cost=candidate_assignment_cost(candidate),
            )
        )

    groups = []
    for courier_id, options in options_by_courier.items():
        ordered_options = tuple(
            sorted(
                options,
                key=lambda option: (
                    -len(option.task_indexes),
                    option.assignment_cost,
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
        total_score=evaluation.total_score,
        assignment_count=evaluation.assignment_count,
        signature=evaluation.signature,
    )


def _state_metrics(
    covered_tasks: float,
    assignment_cost: float,
    assigned_task_indexes: FrozenSet[int],
    assignments: Tuple[Assignment, ...],
    total_task_count: int,
) -> _Metrics:
    unassigned_count = total_task_count - len(assigned_task_indexes)
    total_score = assignment_cost + unassigned_count * PENALTY_SCORE
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
    if candidate.total_score != incumbent.total_score:
        return candidate.total_score < incumbent.total_score
    if candidate.assignment_count != incumbent.assignment_count:
        return candidate.assignment_count < incumbent.assignment_count
    return candidate.signature < incumbent.signature
