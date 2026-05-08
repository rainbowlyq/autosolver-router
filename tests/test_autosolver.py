import unittest

from autosolver.evaluator import evaluate_solution
from autosolver.parser import parse_problem
from autosolver.selector import StrategySelector
from autosolver.solver import AutoSolver
from autosolver.strategies import GreedyByScore


class AutoSolverTests(unittest.TestCase):
    def test_autosolver_returns_lowest_penalized_score_solution_and_records_attempts(self):
        instance = parse_problem(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001\tC001\t10.0\t0.5",
                    "T0002\tC002\t11.0\t0.5",
                    "T0001,T0002\tC003\t15.0\t0.9",
                ]
            )
        )
        solver = AutoSolver(time_limit_seconds=1.0)

        solution = solver.solve(instance)

        evaluation = evaluate_solution(instance, solution)
        self.assertTrue(evaluation.valid)
        self.assertAlmostEqual(evaluation.total_score, 33.5)
        self.assertGreaterEqual(len(solver.history), 1)

    def test_autosolver_empty_input_returns_empty_solution(self):
        instance = parse_problem("task_id_list\tcourier_id\ttotal_score\twillingness\n")
        solver = AutoSolver(time_limit_seconds=1.0)

        solution = solver.solve(instance)

        self.assertEqual(solution.assignments, ())

    def test_autosolver_keeps_empty_solution_when_assignment_cost_exceeds_penalty(self):
        instance = parse_problem(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001\tC001\t500.0\t1.0",
                ]
            )
        )
        selector = StrategySelector(strategies=(GreedyByScore(),))
        solver = AutoSolver(time_limit_seconds=1.0, selector=selector)

        solution = solver.solve(instance)

        self.assertEqual(solution.assignments, ())


if __name__ == "__main__":
    unittest.main()
