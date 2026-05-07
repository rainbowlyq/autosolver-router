import unittest

from autosolver.evaluator import evaluate_solution, is_better_solution
from autosolver.models import Assignment, Solution
from autosolver.parser import parse_problem


def make_instance():
    return parse_problem(
        "\n".join(
            [
                "task_id_list\tcourier_id\ttotal_score\twillingness",
                "T0001\tC001\t10.0\t0.5",
                "T0002\tC002\t12.0\t0.5",
                "T0001,T0002\tC003\t30.0\t0.5",
                "T0003\tC001\t1.0\t0.5",
            ]
        )
    )


class EvaluatorTests(unittest.TestCase):
    def test_evaluate_solution_counts_expected_coverage_and_score(self):
        instance = make_instance()
        solution = Solution(
            assignments=(
                Assignment.from_candidate(instance.candidates[0]),
                Assignment.from_candidate(instance.candidates[1]),
            )
        )

        evaluation = evaluate_solution(instance, solution)

        self.assertTrue(evaluation.valid)
        self.assertAlmostEqual(evaluation.covered_tasks, 1.0)
        self.assertAlmostEqual(evaluation.expected_covered_tasks, 1.0)
        self.assertAlmostEqual(evaluation.expected_coverage_rate, 1 / 3)
        self.assertAlmostEqual(evaluation.total_score, 11.0)
        self.assertAlmostEqual(evaluation.expected_total_score, 11.0)
        self.assertAlmostEqual(evaluation.raw_total_score, 22.0)
        self.assertEqual(evaluation.assignment_count, 2)

    def test_evaluate_solution_allows_duplicate_tasks_and_combines_acceptance_probability(self):
        instance = make_instance()
        solution = Solution(
            assignments=(
                Assignment.from_candidate(instance.candidates[0]),
                Assignment.from_candidate(instance.candidates[2]),
            )
        )

        evaluation = evaluate_solution(instance, solution)

        self.assertTrue(evaluation.valid)
        self.assertNotIn("duplicate task T0001", evaluation.errors)
        self.assertAlmostEqual(evaluation.covered_tasks, 1.25)
        self.assertAlmostEqual(evaluation.expected_covered_tasks, 1.25)
        self.assertAlmostEqual(evaluation.total_score, 20.0)
        self.assertAlmostEqual(evaluation.expected_total_score, 20.0)
        self.assertAlmostEqual(evaluation.raw_total_score, 40.0)

    def test_evaluate_solution_rejects_duplicate_couriers(self):
        instance = make_instance()
        solution = Solution(
            assignments=(
                Assignment.from_candidate(instance.candidates[0]),
                Assignment.from_candidate(instance.candidates[3]),
            )
        )

        evaluation = evaluate_solution(instance, solution)

        self.assertFalse(evaluation.valid)
        self.assertIn("duplicate courier C001", evaluation.errors)

    def test_is_better_prioritizes_coverage_before_score(self):
        instance = make_instance()
        incumbent = Solution(assignments=(Assignment.from_candidate(instance.candidates[0]),))
        candidate = Solution(assignments=(Assignment.from_candidate(instance.candidates[2]),))

        self.assertTrue(is_better_solution(instance, candidate, incumbent))

    def test_is_better_uses_lower_score_when_coverage_ties(self):
        instance = make_instance()
        incumbent = Solution(assignments=(Assignment.from_candidate(instance.candidates[2]),))
        candidate = Solution(
            assignments=(
                Assignment.from_candidate(instance.candidates[0]),
                Assignment.from_candidate(instance.candidates[1]),
            )
        )

        self.assertTrue(is_better_solution(instance, candidate, incumbent))


if __name__ == "__main__":
    unittest.main()
