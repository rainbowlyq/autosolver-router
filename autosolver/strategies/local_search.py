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
            kept_couriers = {courier_id for assignment in kept for courier_id in assignment.courier_ids}

            for candidate in instance.candidates:
                if budget.expired():
                    break
                if candidate.courier_id in kept_couriers:
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
