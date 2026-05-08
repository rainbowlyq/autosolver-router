from autosolver.parser import parse_problem, solution_to_output
from autosolver.solver import AutoSolver


def solve(input_text: str) -> list:
    instance = parse_problem(input_text)
    solution = AutoSolver(time_limit_seconds=9.8).solve(instance)
    return solution_to_output(solution)
