import unittest

from autosolver.models import Assignment, Solution
from autosolver.parser import format_output_rows, parse_problem, solution_to_output


class ParserTests(unittest.TestCase):
    def test_parse_problem_skips_header_empty_lines_and_invalid_rows(self):
        input_text = "\n".join(
            [
                "task_id_list\tcourier_id\ttotal_score\twillingness",
                "T0001,T0002\tC001\t12.5\t0.8",
                "",
                "bad\trow",
                "T0003\tC002\tnot-a-number\t0.3",
                "T0004\tC003\t8.25\t0.6",
            ]
        )

        instance = parse_problem(input_text)

        self.assertEqual(len(instance.candidates), 2)
        self.assertEqual(instance.candidates[0].task_id_list, "T0001,T0002")
        self.assertEqual(instance.candidates[0].task_ids, ("T0001", "T0002"))
        self.assertEqual(instance.candidates[0].courier_id, "C001")
        self.assertEqual(instance.candidates[0].total_score, 12.5)
        self.assertEqual(instance.candidates[0].willingness, 0.8)
        self.assertEqual(instance.candidates[1].index, 4)

    def test_solution_to_output_matches_competition_shape(self):
        instance = parse_problem(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001\tC001\t4.0\t0.7",
                ]
            )
        )
        solution = Solution(assignments=(Assignment.from_candidate(instance.candidates[0]),))

        output = solution_to_output(solution)

        self.assertEqual(output, [("T0001", ["C001"])])

    def test_solution_to_output_groups_same_task_list_couriers(self):
        instance = parse_problem(
            "\n".join(
                [
                    "task_id_list\tcourier_id\ttotal_score\twillingness",
                    "T0001\tC001\t4.0\t0.7",
                    "T0001\tC002\t5.0\t0.6",
                ]
            )
        )
        solution = Solution(
            assignments=(
                Assignment.from_candidate(instance.candidates[0]),
                Assignment.from_candidate(instance.candidates[1]),
            )
        )

        output = solution_to_output(solution)

        self.assertEqual(output, [("T0001", ["C001", "C002"])])

    def test_format_output_rows_matches_example_solver_printing(self):
        text = format_output_rows([("T0001,T0002", ["C001"]), ("T0003", ["C002", "C003"])])

        self.assertEqual(text, "T0001,T0002\tC001\nT0003\tC002,C003")


if __name__ == "__main__":
    unittest.main()
