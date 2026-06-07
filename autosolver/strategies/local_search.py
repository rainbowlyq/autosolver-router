from time import perf_counter
from typing import Optional

from autosolver.budget import TimeBudget
from autosolver.evaluator import is_better_solution
from autosolver.models import Assignment, ProblemInstance, Solution
from autosolver.strategies.greedy import GreedyByScore


class LocalRepair:
    name = "local_repair"

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Optional[Solution],
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
    ) -> Optional[Solution]:
        best_candidate_solution = None
        assignments = list(incumbent.assignments)

        for remove_index in range(len(assignments)):
            if budget.expired():
                break

            kept = assignments[:remove_index] + assignments[remove_index + 1 :]
            kept_couriers = {courier_id for assignment in kept for courier_id in assignment.courier_ids}
            kept_tasks = {task_id for assignment in kept for task_id in assignment.task_ids}

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


class PairSwapRepair:
    name = "pair_swap_repair"

    def __init__(self, max_seconds: float = 2.0) -> None:
        self.max_seconds = max(0.0, max_seconds)

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Optional[Solution],
        budget: TimeBudget,
    ) -> Solution:
        if incumbent is None or not incumbent.assignments:
            return Solution.empty()

        started_at = perf_counter()

        def expired() -> bool:
            return budget.expired() or perf_counter() - started_at >= self.max_seconds

        candidate_by_output_key = {
            (candidate.task_id_list, candidate.courier_id): candidate
            for candidate in instance.candidates
        }
        best = incumbent
        improved = True

        while improved and not expired():
            improved = False
            best_trial = None
            assignments = list(best.assignments)

            for left_index in range(len(assignments)):
                if expired():
                    break
                left = assignments[left_index]
                left_courier = left.candidate.courier_id

                for right_index in range(left_index + 1, len(assignments)):
                    if expired():
                        break
                    right = assignments[right_index]
                    if left.task_id_list == right.task_id_list:
                        continue

                    right_courier = right.candidate.courier_id
                    replacement_left = candidate_by_output_key.get(
                        (left.task_id_list, right_courier)
                    )
                    replacement_right = candidate_by_output_key.get(
                        (right.task_id_list, left_courier)
                    )
                    if replacement_left is None or replacement_right is None:
                        continue

                    trial_assignments = list(assignments)
                    trial_assignments[left_index] = Assignment.from_candidate(replacement_left)
                    trial_assignments[right_index] = Assignment.from_candidate(replacement_right)
                    trial = Solution(assignments=tuple(trial_assignments))

                    if not is_better_solution(instance, trial, best):
                        continue
                    if best_trial is None or is_better_solution(instance, trial, best_trial):
                        best_trial = trial

            if best_trial is not None:
                best = best_trial
                improved = True

        return best
