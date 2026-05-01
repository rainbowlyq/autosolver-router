import unittest

from solver import solve


class SolverContractTests(unittest.TestCase):
    def test_solve_returns_example_solver_shape(self):
        output = solve(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001\tC001\t10.0\t0.5",
                    "T0002\tC002\t11.0\t0.5",
                ]
            )
        )

        self.assertIsInstance(output, list)
        self.assertEqual(output, [("T0001", ["C001"]), ("T0002", ["C002"])])

    def test_solve_handles_empty_input(self):
        self.assertEqual(solve(""), [])


if __name__ == "__main__":
    unittest.main()
