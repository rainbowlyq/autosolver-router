from typing import Optional, Tuple

from autosolver.budget import TimeBudget
from autosolver.models import AttemptRecord
from autosolver.strategies import (
    BeamSetPackingSearch,
    ExactBranchAndBound,
    GreedyByCoverage,
    GreedyByExpectedScore,
    GreedyByScore,
    GreedyCoverageAware,
    LocalRepair,
    MarginalSavingsGreedy,
    PairSwapRepair,
    PressureCoverageGreedy,
    ReinforceGreedy,
    SingletonBeamReassignment,
    SingletonMatchingGreedy,
    Strategy,
)


class StrategySelector:
    def __init__(self, strategies: Optional[Tuple[Strategy, ...]] = None) -> None:
        self._strategies = strategies or (
            GreedyByScore(),
            GreedyByExpectedScore(),
            GreedyByCoverage(),
            GreedyCoverageAware(),
            SingletonMatchingGreedy(),
            SingletonBeamReassignment(),
            MarginalSavingsGreedy(),
            PressureCoverageGreedy(),
            BeamSetPackingSearch(),
            ExactBranchAndBound(),
            ReinforceGreedy(),
            PairSwapRepair(),
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
