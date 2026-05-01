from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Candidate:
    index: int
    task_id_list: str
    task_ids: tuple[str, ...]
    courier_id: str
    total_score: float
    willingness: float


@dataclass(frozen=True, slots=True)
class ProblemInstance:
    candidates: tuple[Candidate, ...]
    task_ids: tuple[str, ...] = field(default_factory=tuple)
    courier_ids: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_candidates(cls, candidates: tuple[Candidate, ...]) -> "ProblemInstance":
        task_ids = sorted({task_id for candidate in candidates for task_id in candidate.task_ids})
        courier_ids = sorted({candidate.courier_id for candidate in candidates})
        return cls(
            candidates=tuple(candidates),
            task_ids=tuple(task_ids),
            courier_ids=tuple(courier_ids),
        )


@dataclass(frozen=True, slots=True)
class Assignment:
    candidate: Candidate
    courier_ids: tuple[str, ...]

    @classmethod
    def from_candidate(cls, candidate: Candidate) -> "Assignment":
        return cls(candidate=candidate, courier_ids=(candidate.courier_id,))

    @property
    def task_id_list(self) -> str:
        return self.candidate.task_id_list

    @property
    def task_ids(self) -> tuple[str, ...]:
        return self.candidate.task_ids

    @property
    def total_score(self) -> float:
        return self.candidate.total_score


@dataclass(frozen=True, slots=True)
class Solution:
    assignments: tuple[Assignment, ...]

    @classmethod
    def empty(cls) -> "Solution":
        return cls(assignments=())


@dataclass(frozen=True, slots=True)
class AttemptRecord:
    strategy_name: str
    elapsed_seconds: float
    valid: bool
    improved: bool
    covered_tasks: int
    total_score: float
    error: str = ""
