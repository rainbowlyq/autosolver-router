from collections import defaultdict
from typing import Optional

from autosolver.budget import TimeBudget
from autosolver.evaluator import _group_assignment_cost, candidate_assignment_cost
from autosolver.models import Assignment, Candidate, ProblemInstance, Solution


def _safe_willingness(candidate: Candidate) -> float:
    return max(candidate.willingness, 0.01)


def _build_unique_task_package_solution(
    ordered_candidates,
    budget: TimeBudget,
) -> Solution:
    used_couriers = set()
    used_task_packages = set()
    used_tasks = set()
    assignments = []

    for candidate in ordered_candidates:
        if budget.expired():
            break
        if candidate.courier_id in used_couriers:
            continue
        if candidate.task_id_list in used_task_packages:
            continue
        if any(task_id in used_tasks for task_id in candidate.task_ids):
            continue

        assignments.append(Assignment.from_candidate(candidate))
        used_couriers.add(candidate.courier_id)
        used_task_packages.add(candidate.task_id_list)
        used_tasks.update(candidate.task_ids)

    return Solution(assignments=tuple(assignments))


class GreedyByExpectedScore:
    name = "greedy_by_expected_score"

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Optional[Solution],
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
        return _build_unique_task_package_solution(ordered, budget)


class GreedyByCoverage:
    name = "greedy_by_coverage"

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Optional[Solution],
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
        return _build_unique_task_package_solution(ordered, budget)


class GreedyCoverageAware:
    name = "greedy_coverage_aware"

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Optional[Solution],
        budget: TimeBudget,
    ) -> Solution:
        candidates_by_size = defaultdict(list)
        for candidate in instance.candidates:
            candidates_by_size[len(candidate.task_ids)].append(candidate)

        for size in candidates_by_size:
            candidates_by_size[size].sort(
                key=lambda candidate: (
                    candidate_assignment_cost(candidate),
                    candidate.task_id_list,
                    candidate.courier_id,
                    candidate.index,
                )
            )

        used_couriers = set()
        covered_tasks = set()
        assignments = []

        for size in sorted(candidates_by_size.keys(), reverse=True):
            if budget.expired():
                break
            for candidate in candidates_by_size[size]:
                if budget.expired():
                    break
                if candidate.courier_id in used_couriers:
                    continue
                candidate_tasks = set(candidate.task_ids)
                if not candidate_tasks & covered_tasks:
                    assignments.append(Assignment.from_candidate(candidate))
                    used_couriers.add(candidate.courier_id)
                    covered_tasks.update(candidate_tasks)

        return Solution(assignments=tuple(assignments))


class ReinforceGreedy:
    name = "reinforce_greedy"

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Optional[Solution],
        budget: TimeBudget,
    ) -> Solution:
        if incumbent is None or not incumbent.assignments:
            return Solution.empty()

        assignments = list(incumbent.assignments)
        used_couriers = {courier_id for a in assignments for courier_id in a.courier_ids}

        candidates_by_courier = defaultdict(list)
        for candidate in instance.candidates:
            if candidate.courier_id not in used_couriers:
                candidates_by_courier[candidate.courier_id].append(candidate)

        task_groups = {}
        for a in assignments:
            task_groups.setdefault(a.candidate.task_id_list, []).append(a.candidate)

        improved = True
        while improved and not budget.expired():
            improved = False
            best_candidate = None
            best_saving = 0.0

            for cid, cands in candidates_by_courier.items():
                if cid in used_couriers:
                    continue
                for candidate in cands:
                    group = task_groups.get(candidate.task_id_list)
                    if group is None:
                        continue
                    old_cost = _group_assignment_cost(group)
                    new_cost = _group_assignment_cost(group + [candidate])
                    saving = old_cost - new_cost
                    if saving > best_saving:
                        best_saving = saving
                        best_candidate = candidate

            if best_candidate is not None and best_saving > 0:
                assignments.append(Assignment.from_candidate(best_candidate))
                used_couriers.add(best_candidate.courier_id)
                task_groups.setdefault(best_candidate.task_id_list, []).append(best_candidate)
                improved = True

        return Solution(assignments=tuple(assignments))
