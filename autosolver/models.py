from typing import NamedTuple, Tuple


class Candidate(NamedTuple):
    index: int
    task_id_list: str
    task_ids: Tuple[str, ...]
    courier_id: str
    total_score: float
    willingness: float


class ProblemInstance(NamedTuple):
    candidates: Tuple[Candidate, ...]
    task_ids: Tuple[str, ...] = ()
    courier_ids: Tuple[str, ...] = ()

    @classmethod
    def from_candidates(cls, candidates: Tuple[Candidate, ...]) -> "ProblemInstance":
        task_ids = sorted({task_id for candidate in candidates for task_id in candidate.task_ids})
        courier_ids = sorted({candidate.courier_id for candidate in candidates})
        return cls(
            candidates=tuple(candidates),
            task_ids=tuple(task_ids),
            courier_ids=tuple(courier_ids),
        )


class Assignment(NamedTuple):
    candidate: Candidate
    courier_ids: Tuple[str, ...]

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


class Solution(NamedTuple):
    assignments: Tuple[Assignment, ...]

    @classmethod
    def empty(cls) -> "Solution":
        return cls(assignments=())


class AttemptRecord(NamedTuple):
    strategy_name: str
    elapsed_seconds: float
    valid: bool
    improved: bool
    covered_tasks: float
    total_score: float
    error: str = ""
