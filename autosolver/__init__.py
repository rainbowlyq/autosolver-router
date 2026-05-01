"""AutoSolver framework package."""

from autosolver.models import Assignment, Candidate, ProblemInstance, Solution
from autosolver.solver import AutoSolver

__all__ = ["Assignment", "AutoSolver", "Candidate", "ProblemInstance", "Solution"]
