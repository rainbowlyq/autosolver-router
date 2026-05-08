from typing import Dict, List, Optional, Tuple

from autosolver.models import Candidate, ProblemInstance, Solution


PENALTY_SCORE = 100.0


class Evaluation:
    __slots__ = (
        "valid",
        "expected_covered_tasks",
        "expected_coverage_rate",
        "expected_total_score",
        "raw_total_score",
        "assignment_cost",
        "unassigned_count",
        "unassigned_penalty",
        "assignment_count",
        "signature",
        "errors",
    )

    def __init__(
        self,
        valid: bool,
        expected_covered_tasks: float,
        expected_coverage_rate: float,
        expected_total_score: float,
        raw_total_score: float,
        assignment_cost: float,
        unassigned_count: int,
        unassigned_penalty: float,
        assignment_count: int,
        signature: Tuple[str, ...],
        errors: Tuple[str, ...] = (),
    ) -> None:
        self.valid = valid
        self.expected_covered_tasks = expected_covered_tasks
        self.expected_coverage_rate = expected_coverage_rate
        self.expected_total_score = expected_total_score
        self.raw_total_score = raw_total_score
        self.assignment_cost = assignment_cost
        self.unassigned_count = unassigned_count
        self.unassigned_penalty = unassigned_penalty
        self.assignment_count = assignment_count
        self.signature = signature
        self.errors = errors

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
        + (1.0 - p_complete) * PENALTY_SCORE * len(candidate.task_ids)
    )


def _group_acceptance_probability(candidates: List[Candidate]) -> float:
    miss_probability = 1.0
    for candidate in candidates:
        miss_probability *= 1.0 - _acceptance_probability(candidate)
    return 1.0 - miss_probability


def _group_expected_score(candidates: List[Candidate]) -> float:
    total_probability = sum(_acceptance_probability(candidate) for candidate in candidates)
    if total_probability <= 0.0:
        return 0.0
    return sum(
        _acceptance_probability(candidate) * candidate.total_score
        for candidate in candidates
    ) / total_probability


def _group_assignment_cost(candidates: List[Candidate]) -> float:
    if not candidates:
        return 0.0
    p_complete = _group_acceptance_probability(candidates)
    expected_score = _group_expected_score(candidates)
    return (
        p_complete * expected_score
        + (1.0 - p_complete) * PENALTY_SCORE * len(candidates[0].task_ids)
    )


def evaluate_solution(instance: ProblemInstance, solution: Solution) -> Evaluation:
    known_candidate_indexes = {candidate.index for candidate in instance.candidates}
    known_tasks = set(instance.task_ids)
    miss_probability_by_task = {task_id: 1.0 for task_id in instance.task_ids}
    used_couriers = set()
    assigned_tasks = set()
    candidates_by_task_list = {}  # type: Dict[str, List[Candidate]]
    courier_ids_by_task_list = {}  # type: Dict[str, List[str]]
    errors = []
    raw_total_score = 0.0

    for assignment in solution.assignments:
        candidate = assignment.candidate
        if candidate.index not in known_candidate_indexes:
            errors.append(f"unknown candidate index {candidate.index}")

        raw_total_score += candidate.total_score
        candidates_by_task_list.setdefault(candidate.task_id_list, []).append(candidate)
        courier_ids_by_task_list.setdefault(candidate.task_id_list, []).extend(assignment.courier_ids)

        for courier_id in assignment.courier_ids:
            if courier_id in used_couriers:
                errors.append(f"duplicate courier {courier_id}")
            used_couriers.add(courier_id)

    assignment_cost = 0.0
    signature = []
    for task_id_list, candidates in candidates_by_task_list.items():
        assignment_cost += _group_assignment_cost(candidates)
        group_acceptance_probability = _group_acceptance_probability(candidates)
        signature.append(f"{task_id_list}\t{','.join(courier_ids_by_task_list[task_id_list])}")

        for task_id in candidates[0].task_ids:
            if task_id in known_tasks:
                miss_probability_by_task[task_id] *= 1.0 - group_acceptance_probability
                assigned_tasks.add(task_id)

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
