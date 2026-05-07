import unittest

from autosolver.evaluator import evaluate_solution
from autosolver.parser import parse_problem
from autosolver.solver import AutoSolver


class AutoSolverTests(unittest.TestCase):
    def test_autosolver_returns_valid_solution_and_records_attempts(self):
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
        self.assertAlmostEqual(evaluation.covered_tasks, 1.9)
        self.assertGreaterEqual(len(solver.history), 1)

    def test_autosolver_empty_input_returns_empty_solution(self):
        instance = parse_problem("task_id_list\tcourier_id\ttotal_score\twillingness\n")
        solver = AutoSolver(time_limit_seconds=1.0)

        solution = solver.solve(instance)

        self.assertEqual(solution.assignments, ())


if __name__ == "__main__":
    unittest.main()
