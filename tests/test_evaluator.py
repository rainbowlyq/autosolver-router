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
    def test_evaluate_solution_counts_expected_coverage_and_penalized_score(self):
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
        self.assertAlmostEqual(evaluation.total_score, 211.0)
        self.assertAlmostEqual(evaluation.expected_total_score, 211.0)
        self.assertAlmostEqual(evaluation.assignment_cost, 111.0)
        self.assertEqual(evaluation.unassigned_count, 1)
        self.assertAlmostEqual(evaluation.unassigned_penalty, 100.0)
        self.assertAlmostEqual(evaluation.raw_total_score, 22.0)
        self.assertEqual(evaluation.assignment_count, 2)

    def test_evaluate_solution_rejects_overlapping_task_batches(self):
        instance = make_instance()
        solution = Solution(
            assignments=(
                Assignment.from_candidate(instance.candidates[0]),
                Assignment.from_candidate(instance.candidates[2]),
            )
        )

        evaluation = evaluate_solution(instance, solution)

        self.assertFalse(evaluation.valid)
        self.assertIn("duplicate task T0001", evaluation.errors)
        self.assertAlmostEqual(evaluation.covered_tasks, 1.25)
        self.assertAlmostEqual(evaluation.expected_covered_tasks, 1.25)
        self.assertAlmostEqual(evaluation.total_score, 270.0)
        self.assertAlmostEqual(evaluation.expected_total_score, 270.0)
        self.assertAlmostEqual(evaluation.assignment_cost, 170.0)
        self.assertEqual(evaluation.unassigned_count, 1)
        self.assertAlmostEqual(evaluation.raw_total_score, 40.0)

    def test_evaluate_solution_allows_same_task_batch_multiple_couriers(self):
        instance = parse_problem(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001,T0002\tC001\t10.0\t0.5",
                    "T0001,T0002\tC002\t20.0\t0.5",
                ]
            )
        )
        solution = Solution(
            assignments=(
                Assignment.from_candidate(instance.candidates[0]),
                Assignment.from_candidate(instance.candidates[1]),
            )
        )

        evaluation = evaluate_solution(instance, solution)

        self.assertTrue(evaluation.valid)
        self.assertNotIn("duplicate task T0001", evaluation.errors)
        self.assertNotIn("duplicate task T0002", evaluation.errors)
        self.assertAlmostEqual(evaluation.expected_covered_tasks, 1.5)
        self.assertAlmostEqual(evaluation.assignment_cost, 61.25)
        self.assertAlmostEqual(evaluation.total_score, 61.25)

    def test_evaluate_solution_rejects_same_task_assigned_through_different_batches(self):
        instance = parse_problem(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001,T0002\tC001\t10.0\t0.5",
                    "T0001,T0003\tC002\t20.0\t0.5",
                ]
            )
        )
        solution = Solution(
            assignments=(
                Assignment.from_candidate(instance.candidates[0]),
                Assignment.from_candidate(instance.candidates[1]),
            )
        )

        evaluation = evaluate_solution(instance, solution)

        self.assertFalse(evaluation.valid)
        self.assertIn("duplicate task T0001", evaluation.errors)

    def test_evaluate_solution_uses_task_count_for_bundle_rejection_penalty(self):
        instance = make_instance()
        solution = Solution(
            assignments=(Assignment.from_candidate(instance.candidates[2]),)
        )

        evaluation = evaluate_solution(instance, solution)

        self.assertTrue(evaluation.valid)
        self.assertAlmostEqual(evaluation.assignment_cost, 115.0)
        self.assertAlmostEqual(evaluation.total_score, 215.0)

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

    def test_is_better_minimizes_penalized_score_before_coverage(self):
        instance = parse_problem(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001\tC001\t10.0\t1.0",
                    "T0001,T0002\tC002\t300.0\t1.0",
                ]
            )
        )
        incumbent = Solution(assignments=(Assignment.from_candidate(instance.candidates[1]),))
        candidate = Solution(assignments=(Assignment.from_candidate(instance.candidates[0]),))

        self.assertTrue(is_better_solution(instance, candidate, incumbent))

    def test_is_better_uses_lower_penalized_score(self):
        instance = parse_problem(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001\tC001\t10.0\t0.5",
                    "T0002\tC002\t12.0\t0.5",
                    "T0001,T0002\tC003\t20.0\t0.5",
                ]
            )
        )
        incumbent = Solution(
            assignments=(
                Assignment.from_candidate(instance.candidates[0]),
                Assignment.from_candidate(instance.candidates[1]),
            )
        )
        candidate = Solution(
            assignments=(Assignment.from_candidate(instance.candidates[2]),)
        )

        self.assertTrue(is_better_solution(instance, candidate, incumbent))


if __name__ == "__main__":
    unittest.main()
