from typing import Optional, Tuple

from autosolver.budget import TimeBudget
from autosolver.models import AttemptRecord
from autosolver.strategies import (
    ExactBranchAndBound,
    GreedyByCoverage,
    GreedyByExpectedScore,
    GreedyByScore,
    GreedyCoverageAware,
    LocalRepair,
    ReinforceGreedy,
    Strategy,
)


class StrategySelector:
    def __init__(self, strategies: Optional[Tuple[Strategy, ...]] = None) -> None:
        self._strategies = strategies or (
            GreedyByScore(),
            GreedyByExpectedScore(),
            GreedyByCoverage(),
            GreedyCoverageAware(),
            ReinforceGreedy(),
            ExactBranchAndBound(),
            LocalRepair(),
        )

    def next_strategy(
        self,
        history: Tuple[AttemptRecord, ...],
        budget: TimeBudget,
    ) -> Optional[Strategy]:
        if budget.expired():
            return None
        if len(history) >= len(self._strategies):
            return None
        return self._strategies[len(history)]
