import unittest

from autosolver.evaluator import evaluate_solution
from autosolver.models import Assignment, Candidate, ProblemInstance, Solution


class ModelTests(unittest.TestCase):
    def test_problem_instance_derives_sorted_task_and_courier_ids(self):
        candidates = (
            Candidate(
                index=0,
                task_id_list="T0002,T0001",
                task_ids=("T0002", "T0001"),
                courier_id="C002",
                total_score=12.5,
                willingness=0.4,
            ),
            Candidate(
                index=1,
                task_id_list="T0003",
                task_ids=("T0003",),
                courier_id="C001",
                total_score=7.0,
                willingness=0.9,
            ),
        )

        instance = ProblemInstance.from_candidates(candidates)

        self.assertEqual(instance.task_ids, ("T0001", "T0002", "T0003"))
        self.assertEqual(instance.courier_ids, ("C001", "C002"))

    def test_assignment_from_candidate_uses_candidate_courier(self):
        candidate = Candidate(
            index=3,
            task_id_list="T0004",
            task_ids=("T0004",),
            courier_id="C007",
            total_score=3.25,
            willingness=0.75,
        )

        assignment = Assignment.from_candidate(candidate)

        self.assertEqual(assignment.task_id_list, "T0004")
        self.assertEqual(assignment.task_ids, ("T0004",))
        self.assertEqual(assignment.courier_ids, ("C007",))
        self.assertEqual(assignment.total_score, 3.25)

    def test_solution_empty_is_valid_shape(self):
        solution = Solution.empty()

        self.assertEqual(solution.assignments, ())

    def test_models_are_not_tuple_subclasses(self):
        candidate = Candidate(
            index=0,
            task_id_list="T0001",
            task_ids=("T0001",),
            courier_id="C001",
            total_score=10.0,
            willingness=0.5,
        )
        instance = ProblemInstance.from_candidates((candidate,))
        assignment = Assignment.from_candidate(candidate)
        solution = Solution(assignments=(assignment,))
        evaluation = evaluate_solution(instance, solution)

        self.assertNotIsInstance(candidate, tuple)
        self.assertNotIsInstance(instance, tuple)
        self.assertNotIsInstance(assignment, tuple)
        self.assertNotIsInstance(solution, tuple)
        self.assertNotIsInstance(evaluation, tuple)


if __name__ == "__main__":
    unittest.main()
