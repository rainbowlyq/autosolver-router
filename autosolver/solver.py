from __future__ import annotations

from time import perf_counter

from autosolver.budget import TimeBudget
from autosolver.evaluator import evaluate_solution, is_better_solution
from autosolver.models import AttemptRecord, ProblemInstance, Solution
from autosolver.selector import StrategySelector


class AutoSolver:
    def __init__(
        self,
        time_limit_seconds: float = 9.5,
        selector: StrategySelector | None = None,
    ) -> None:
        self.time_limit_seconds = time_limit_seconds
        self.selector = selector or StrategySelector()
        self.history: list[AttemptRecord] = []

    def solve(self, instance: ProblemInstance) -> Solution:
        if not instance.candidates:
            return Solution.empty()

        budget = TimeBudget(self.time_limit_seconds)
        incumbent: Solution | None = None

        while not budget.expired():
            strategy = self.selector.next_strategy(tuple(self.history), budget)
            if strategy is None:
                break

            started_at = perf_counter()
            try:
                candidate = strategy.run(instance, incumbent, budget)
                evaluation = evaluate_solution(instance, candidate)
                improved = is_better_solution(instance, candidate, incumbent)
                if improved:
                    incumbent = candidate
                self.history.append(
                    AttemptRecord(
                        strategy_name=strategy.name,
                        elapsed_seconds=perf_counter() - started_at,
                        valid=evaluation.valid,
                        improved=improved,
                        covered_tasks=evaluation.covered_tasks,
                        total_score=evaluation.total_score,
                    )
                )
            except Exception as exc:
                self.history.append(
                    AttemptRecord(
                        strategy_name=strategy.name,
                        elapsed_seconds=perf_counter() - started_at,
                        valid=False,
                        improved=False,
                        covered_tasks=0,
                        total_score=float("inf"),
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )

        return incumbent or Solution.empty()
