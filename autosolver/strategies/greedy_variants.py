from __future__ import annotations

from autosolver.budget import TimeBudget
from autosolver.models import Candidate, ProblemInstance, Solution
from autosolver.strategies.greedy import build_greedy_solution


def _safe_willingness(candidate: Candidate) -> float:
    return max(candidate.willingness, 0.01)


class GreedyByExpectedScore:
    name = "greedy_by_expected_score"

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Solution | None,
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
        return build_greedy_solution(instance, ordered, budget)


class GreedyByCoverage:
    name = "greedy_by_coverage"

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Solution | None,
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
        return build_greedy_solution(instance, ordered, budget)
