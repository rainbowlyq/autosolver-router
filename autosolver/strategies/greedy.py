from typing import Callable, Iterable, Optional, Tuple

from autosolver.budget import TimeBudget
from autosolver.models import Assignment, Candidate, ProblemInstance, Solution

CandidateKey = Callable[[Candidate], Tuple]


def build_greedy_solution(
    instance: ProblemInstance,
    ordered_candidates: Iterable[Candidate],
    budget: TimeBudget,
) -> Solution:
    used_couriers = set()
    task_batches = {}
    assignments = []

    for candidate in ordered_candidates:
        if budget.expired():
            break
        if candidate.courier_id in used_couriers:
            continue
        if any(
            task_id in task_batches
            and candidate.task_id_list not in task_batches[task_id]
            for task_id in candidate.task_ids
        ):
            continue

        assignments.append(Assignment.from_candidate(candidate))
        used_couriers.add(candidate.courier_id)
        for task_id in candidate.task_ids:
            task_batches.setdefault(task_id, set()).add(candidate.task_id_list)

    return Solution(assignments=tuple(assignments))


class GreedyByScore:
    name = "greedy_by_score"

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Optional[Solution],
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
