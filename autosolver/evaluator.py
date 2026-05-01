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
