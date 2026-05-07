from typing import Optional

from autosolver.budget import TimeBudget
from autosolver.models import ProblemInstance, Solution


class Strategy:
    name = ""

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Optional[Solution],
        budget: TimeBudget,
    ) -> Solution:
        raise NotImplementedError
