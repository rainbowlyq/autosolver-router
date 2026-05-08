from typing import NamedTuple, Optional, Tuple

from autosolver.models import Candidate, ProblemInstance, Solution


PENALTY_SCORE = 100.0


class Evaluation(NamedTuple):
    valid: bool
    expected_covered_tasks: float
    expected_coverage_rate: float
    expected_total_score: float
    raw_total_score: float
    assignment_cost: float
    unassigned_count: int
    unassigned_penalty: float
    assignment_count: int
    signature: Tuple[str, ...]
    errors: Tuple[str, ...] = ()

    @property
    def covered_tasks(self) -> float:
        return self.expected_covered_tasks

    @property
    def total_score(self) -> float:
        return self.expected_total_score


def _acceptance_probability(candidate: Candidate) -> float:
    return min(max(candidate.willingness, 0.0), 1.0)


def candidate_assignment_cost(candidate: Candidate) -> float:
    p_complete = _acceptance_probability(candidate)
    return (
        p_complete * candidate.total_score
        + (1.0 - p_complete) * PENALTY_SCORE
    )


def evaluate_solution(instance: ProblemInstance, solution: Solution) -> Evaluation:
    known_candidate_indexes = {candidate.index for candidate in instance.candidates}
    known_tasks = set(instance.task_ids)
    miss_probability_by_task = {task_id: 1.0 for task_id in instance.task_ids}
    used_couriers = set()
    assigned_tasks = set()
    errors = []
    assignment_cost = 0.0
    raw_total_score = 0.0
    signature = []

    for assignment in solution.assignments:
        candidate = assignment.candidate
        if candidate.index not in known_candidate_indexes:
            errors.append(f"unknown candidate index {candidate.index}")

        acceptance_probability = _acceptance_probability(candidate)
        raw_total_score += candidate.total_score
        assignment_cost += candidate_assignment_cost(candidate)
        signature.append(f"{candidate.task_id_list}\t{','.join(assignment.courier_ids)}")

        for task_id in candidate.task_ids:
            if task_id in known_tasks:
                miss_probability_by_task[task_id] *= 1.0 - acceptance_probability
                assigned_tasks.add(task_id)

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
    unassigned_count = len(known_tasks - assigned_tasks)
    unassigned_penalty = unassigned_count * PENALTY_SCORE
    expected_total_score = assignment_cost + unassigned_penalty

    return Evaluation(
        valid=not errors,
        expected_covered_tasks=round(expected_covered_tasks, 12),
        expected_coverage_rate=round(expected_coverage_rate, 12),
        expected_total_score=round(expected_total_score, 12),
        raw_total_score=round(raw_total_score, 12),
        assignment_cost=round(assignment_cost, 12),
        unassigned_count=unassigned_count,
        unassigned_penalty=round(unassigned_penalty, 12),
        assignment_count=len(solution.assignments),
        signature=tuple(sorted(signature)),
        errors=tuple(errors),
    )


def is_better_solution(
    instance: ProblemInstance,
    candidate: Solution,
    incumbent: Optional[Solution],
) -> bool:
    candidate_eval = evaluate_solution(instance, candidate)
    if not candidate_eval.valid:
        return False

    if incumbent is None:
        return True

    incumbent_eval = evaluate_solution(instance, incumbent)
    if not incumbent_eval.valid:
        return True

    if candidate_eval.expected_total_score != incumbent_eval.expected_total_score:
        return candidate_eval.expected_total_score < incumbent_eval.expected_total_score

    if candidate_eval.assignment_count != incumbent_eval.assignment_count:
        return candidate_eval.assignment_count < incumbent_eval.assignment_count

    return candidate_eval.signature < incumbent_eval.signature
