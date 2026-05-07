from __future__ import annotations

from dataclasses import dataclass

from autosolver.models import Candidate, ProblemInstance, Solution


@dataclass(frozen=True, slots=True)
class Evaluation:
    valid: bool
    expected_covered_tasks: float
    expected_coverage_rate: float
    expected_total_score: float
    raw_total_score: float
    assignment_count: int
    signature: tuple[str, ...]
    errors: tuple[str, ...] = ()

    @property
    def covered_tasks(self) -> float:
        return self.expected_covered_tasks

    @property
    def total_score(self) -> float:
        return self.expected_total_score


def _acceptance_probability(candidate: Candidate) -> float:
    return min(max(candidate.willingness, 0.0), 1.0)


def evaluate_solution(instance: ProblemInstance, solution: Solution) -> Evaluation:
    known_candidate_indexes = {candidate.index for candidate in instance.candidates}
    known_tasks = set(instance.task_ids)
    miss_probability_by_task = {task_id: 1.0 for task_id in instance.task_ids}
    used_couriers: set[str] = set()
    errors: list[str] = []
    expected_total_score = 0.0
    raw_total_score = 0.0
    signature: list[str] = []

    for assignment in solution.assignments:
        candidate = assignment.candidate
        if candidate.index not in known_candidate_indexes:
            errors.append(f"unknown candidate index {candidate.index}")

        acceptance_probability = _acceptance_probability(candidate)
        raw_total_score += candidate.total_score
        expected_total_score += candidate.total_score * acceptance_probability
        signature.append(f"{candidate.task_id_list}\t{','.join(assignment.courier_ids)}")

        for task_id in candidate.task_ids:
            if task_id in known_tasks:
                miss_probability_by_task[task_id] *= 1.0 - acceptance_probability

        for courier_id in assignment.courier_ids:
            if courier_id in used_couriers:
                errors.append(f"duplicate courier {courier_id}")
            used_couriers.add(courier_id)

    # Assumes independent acceptance events for couriers assigned to the same task.
    expected_covered_tasks = sum(
        1.0 - miss_probability
        for miss_probability in miss_probability_by_task.values()
    )
    expected_coverage_rate = (
        expected_covered_tasks / len(instance.task_ids)
        if instance.task_ids
        else 0.0
    )

    return Evaluation(
        valid=not errors,
        expected_covered_tasks=round(expected_covered_tasks, 12),
        expected_coverage_rate=round(expected_coverage_rate, 12),
        expected_total_score=round(expected_total_score, 12),
        raw_total_score=round(raw_total_score, 12),
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

    if candidate_eval.expected_covered_tasks != incumbent_eval.expected_covered_tasks:
        return candidate_eval.expected_covered_tasks > incumbent_eval.expected_covered_tasks

    if candidate_eval.expected_total_score != incumbent_eval.expected_total_score:
        return candidate_eval.expected_total_score < incumbent_eval.expected_total_score

    if candidate_eval.assignment_count != incumbent_eval.assignment_count:
        return candidate_eval.assignment_count < incumbent_eval.assignment_count

    return candidate_eval.signature < incumbent_eval.signature
