from __future__ import annotations

from typing import Protocol

from autosolver.budget import TimeBudget
from autosolver.models import ProblemInstance, Solution


class Strategy(Protocol):
    name: str

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Solution | None,
        budget: TimeBudget,
    ) -> Solution:
        ...
