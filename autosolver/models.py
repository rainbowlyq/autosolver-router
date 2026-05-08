from typing import Tuple


class Candidate:
    __slots__ = ("index", "task_id_list", "task_ids", "courier_id", "total_score", "willingness")

    def __init__(
        self,
        index: int,
        task_id_list: str,
        task_ids: Tuple[str, ...],
        courier_id: str,
        total_score: float,
        willingness: float,
    ) -> None:
        self.index = index
        self.task_id_list = task_id_list
        self.task_ids = task_ids
        self.courier_id = courier_id
        self.total_score = total_score
        self.willingness = willingness


class ProblemInstance:
    __slots__ = ("candidates", "task_ids", "courier_ids")

    def __init__(
        self,
        candidates: Tuple[Candidate, ...],
        task_ids: Tuple[str, ...] = (),
        courier_ids: Tuple[str, ...] = (),
    ) -> None:
        self.candidates = candidates
        self.task_ids = task_ids
        self.courier_ids = courier_ids

    @classmethod
    def from_candidates(cls, candidates: Tuple[Candidate, ...]) -> "ProblemInstance":
        task_ids = sorted({task_id for candidate in candidates for task_id in candidate.task_ids})
        courier_ids = sorted({candidate.courier_id for candidate in candidates})
        return cls(
            candidates=tuple(candidates),
            task_ids=tuple(task_ids),
            courier_ids=tuple(courier_ids),
        )


class Assignment:
    __slots__ = ("candidate", "courier_ids")

    def __init__(self, candidate: Candidate, courier_ids: Tuple[str, ...]) -> None:
        self.candidate = candidate
        self.courier_ids = courier_ids

    @classmethod
    def from_candidate(cls, candidate: Candidate) -> "Assignment":
        return cls(candidate=candidate, courier_ids=(candidate.courier_id,))

    @property
    def task_id_list(self) -> str:
        return self.candidate.task_id_list

    @property
    def task_ids(self) -> Tuple[str, ...]:
        return self.candidate.task_ids

    @property
    def total_score(self) -> float:
        return self.candidate.total_score


class Solution:
    __slots__ = ("assignments",)

    def __init__(self, assignments: Tuple[Assignment, ...]) -> None:
        self.assignments = assignments

    @classmethod
    def empty(cls) -> "Solution":
        return cls(assignments=())


class AttemptRecord:
    __slots__ = (
        "strategy_name",
        "elapsed_seconds",
        "valid",
        "improved",
        "covered_tasks",
        "total_score",
        "error",
    )

    def __init__(
        self,
        strategy_name: str,
        elapsed_seconds: float,
        valid: bool,
        improved: bool,
        covered_tasks: float,
        total_score: float,
        error: str = "",
    ) -> None:
        self.strategy_name = strategy_name
        self.elapsed_seconds = elapsed_seconds
        self.valid = valid
        self.improved = improved
        self.covered_tasks = covered_tasks
        self.total_score = total_score
        self.error = error
