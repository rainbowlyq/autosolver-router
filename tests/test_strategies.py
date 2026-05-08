import unittest

from autosolver.budget import TimeBudget
from autosolver.evaluator import evaluate_solution
from autosolver.models import AttemptRecord
from autosolver.parser import parse_problem
from autosolver.selector import StrategySelector
import autosolver.strategies as strategies
from autosolver.strategies import (
    GreedyByCoverage,
    GreedyByExpectedScore,
    GreedyByScore,
    LocalRepair,
)


class StrategyTests(unittest.TestCase):
    def test_greedy_by_score_matches_baseline_choice_order(self):
        instance = parse_problem(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001\tC001\t20.0\t0.5",
                    "T0001,T0002\tC002\t5.0\t0.5",
                    "T0003\tC001\t1.0\t0.5",
                ]
            )
        )

        solution = GreedyByScore().run(instance, None, TimeBudget(1.0))

        self.assertEqual(
            [(assignment.task_id_list, assignment.courier_ids) for assignment in solution.assignments],
            [("T0003", ("C001",)), ("T0001,T0002", ("C002",))],
        )

    def test_greedy_by_score_allows_multiple_couriers_for_same_task(self):
        instance = parse_problem(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001\tC001\t1.0\t0.5",
                    "T0001\tC002\t2.0\t0.6",
                ]
            )
        )

        solution = GreedyByScore().run(instance, None, TimeBudget(1.0))

        self.assertEqual(
            [(assignment.task_id_list, assignment.courier_ids) for assignment in solution.assignments],
            [("T0001", ("C001",)), ("T0001", ("C002",))],
        )

    def test_greedy_by_score_allows_overlapping_task_packages(self):
        instance = parse_problem(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001\tC001\t1.0\t0.5",
                    "T0001,T0002\tC002\t2.0\t0.6",
                ]
            )
        )

        solution = GreedyByScore().run(instance, None, TimeBudget(1.0))

        self.assertEqual(
            [(assignment.task_id_list, assignment.courier_ids) for assignment in solution.assignments],
            [("T0001", ("C001",)), ("T0001,T0002", ("C002",))],
        )

    def test_greedy_variants_return_valid_solutions(self):
        instance = parse_problem(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001\tC001\t10.0\t0.9",
                    "T0002\tC002\t9.0\t0.1",
                    "T0001,T0002\tC003\t15.0\t0.8",
                ]
            )
        )

        for strategy in (GreedyByExpectedScore(), GreedyByCoverage()):
            with self.subTest(strategy=strategy.name):
                solution = strategy.run(instance, None, TimeBudget(1.0))
                evaluation = evaluate_solution(instance, solution)
                self.assertTrue(evaluation.valid)
                self.assertGreaterEqual(evaluation.covered_tasks, 1)

    def test_local_repair_keeps_or_improves_valid_incumbent(self):
        instance = parse_problem(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001\tC001\t10.0\t0.5",
                    "T0002\tC002\t10.0\t0.5",
                    "T0001,T0002\tC003\t15.0\t0.5",
                ]
            )
        )
        incumbent = GreedyByScore().run(instance, None, TimeBudget(1.0))

        repaired = LocalRepair().run(instance, incumbent, TimeBudget(1.0))

        self.assertTrue(evaluate_solution(instance, repaired).valid)

    def test_exact_branch_and_bound_minimizes_penalized_score(self):
        exact_strategy_class = getattr(strategies, "ExactBranchAndBound", None)
        self.assertIsNotNone(exact_strategy_class)
        instance = parse_problem(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001\tC001\t10.0\t1.0",
                    "T0002\tC002\t500.0\t1.0",
                ]
            )
        )
        incumbent = GreedyByScore().run(instance, None, TimeBudget(1.0))

        solution = exact_strategy_class().run(instance, incumbent, TimeBudget(1.0))

        evaluation = evaluate_solution(instance, solution)
        self.assertTrue(evaluation.valid)
        self.assertAlmostEqual(evaluation.total_score, 110.0)
        self.assertEqual(
            {(assignment.task_id_list, assignment.courier_ids) for assignment in solution.assignments},
            {("T0001", ("C001",))},
        )

    def test_default_selector_includes_exact_branch_and_bound(self):
        selector = StrategySelector()
        budget = TimeBudget(1.0)
        history = []
        names = []

        while True:
            strategy = selector.next_strategy(tuple(history), budget)
            if strategy is None:
                break
            names.append(strategy.name)
            history.append(
                AttemptRecord(
                    strategy_name=strategy.name,
                    elapsed_seconds=0.0,
                    valid=True,
                    improved=False,
                    covered_tasks=0.0,
                    total_score=0.0,
                )
            )

        self.assertIn("exact_branch_and_bound", names)
        self.assertLess(names.index("exact_branch_and_bound"), names.index("local_repair"))

    def test_exact_branch_and_bound_respects_strategy_time_limit(self):
        exact_strategy_class = getattr(strategies, "ExactBranchAndBound", None)
        self.assertIsNotNone(exact_strategy_class)
        instance = parse_problem(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001\tC001\t1.0\t1.0",
                    "T0001\tC002\t2.0\t1.0",
                    "T0002\tC002\t100.0\t1.0",
                ]
            )
        )
        incumbent = GreedyByScore().run(instance, None, TimeBudget(1.0))

        solution = exact_strategy_class(max_seconds=0.0).run(instance, incumbent, TimeBudget(1.0))

        self.assertEqual(solution.assignments, incumbent.assignments)


if __name__ == "__main__":
    unittest.main()
