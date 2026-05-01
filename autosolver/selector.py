from __future__ import annotations

from autosolver.budget import TimeBudget
from autosolver.models import AttemptRecord
from autosolver.strategies import (
    GreedyByCoverage,
    GreedyByExpectedScore,
    GreedyByScore,
    LocalRepair,
    Strategy,
)


class StrategySelector:
    def __init__(self, strategies: tuple[Strategy, ...] | None = None) -> None:
        self._strategies = strategies or (
            GreedyByScore(),
            GreedyByExpectedScore(),
            GreedyByCoverage(),
            LocalRepair(),
        )

    def next_strategy(
        self,
        history: tuple[AttemptRecord, ...],
        budget: TimeBudget,
    ) -> Strategy | None:
        if budget.expired():
            return None
        if len(history) >= len(self._strategies):
            return None
        return self._strategies[len(history)]
