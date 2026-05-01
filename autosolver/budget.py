from __future__ import annotations

from time import perf_counter


class TimeBudget:
    def __init__(self, limit_seconds: float, safety_margin_seconds: float = 0.05) -> None:
        self.limit_seconds = max(0.0, limit_seconds)
        self.safety_margin_seconds = max(0.0, safety_margin_seconds)
        self.started_at = perf_counter()

    @property
    def elapsed(self) -> float:
        return perf_counter() - self.started_at

    @property
    def remaining(self) -> float:
        return max(0.0, self.limit_seconds - self.elapsed)

    def expired(self) -> bool:
        return self.remaining <= self.safety_margin_seconds

    def has_time_for(self, seconds: float) -> bool:
        return self.remaining > seconds + self.safety_margin_seconds
