import json
import tempfile
import unittest
from importlib import import_module
from pathlib import Path

eval_report = import_module("eval")


class ResultReportTests(unittest.TestCase):
    def test_recompute_detail_cost_uses_completion_expectation_formula(self):
        detail = {
            "task_id_list": "T0005",
            "couriers": ["C000"],
            "p_complete": 0.7324,
            "expected_score": 10.23,
            "cost": 34.2525,
        }

        cost = eval_report.recompute_detail_cost(detail)

        self.assertAlmostEqual(cost, 34.252452, places=6)

    def test_recompute_detail_cost_scales_rejection_penalty_by_task_count(self):
        detail = {
            "task_id_list": "T0011,T0024",
            "couriers": ["C001"],
            "p_complete": 0.8704,
            "expected_score": 23.147,
            "cost": 46.0671,
        }

        cost = eval_report.recompute_detail_cost(detail)

        self.assertAlmostEqual(cost, 46.0671488, places=6)

    def test_analyze_result_payload_uses_penalty_score_for_invalid_cases(self):
        payload = {
            "avg_score": 155.0,
            "success_count": 1,
            "case_results": [
                {
                    "status": "ok",
                    "case_file": "invalid.txt",
                    "validity": False,
                    "total_score": 0.0,
                    "penalty_score": 300.0,
                    "unassigned_count": 0,
                    "detail": [],
                    "errors": ["duplicate task"],
                },
                {
                    "status": "ok",
                    "case_file": "valid.txt",
                    "validity": True,
                    "total_score": 10.0,
                    "unassigned_count": 0,
                    "detail": [
                        {
                            "task_id_list": "T0001",
                            "couriers": ["C001"],
                            "p_complete": 1.0,
                            "expected_score": 10.0,
                            "cost": 10.0,
                        }
                    ],
                },
            ],
        }

        analysis = eval_report.analyze_result_payload(payload)

        self.assertTrue(analysis["formula_matches"])
        self.assertEqual(analysis["recomputed_avg_score"], 155.0)

    def test_analyze_result_payload_reproduces_example_scores(self):
        path = Path("example.json")
        if not path.exists():
            path = Path("results/d4489e42b3234d199798f2215d28cd1e/response.json")
        payload = json.loads(path.read_text(encoding="utf-8"))

        analysis = eval_report.analyze_result_payload(payload)

        self.assertTrue(analysis["formula_matches"])
        self.assertLessEqual(analysis["max_detail_cost_delta"], 0.001)
        self.assertLessEqual(analysis["max_case_score_delta"], 0.001)
        self.assertLessEqual(abs(analysis["avg_score_delta"]), 0.001)
        self.assertEqual(analysis["case_count"], 10)
        self.assertEqual(analysis["success_count"], 10)

    def test_build_tables_flattens_case_and_task_details(self):
        payload = {
            "job_id": "job-1",
            "status": "ok",
            "avg_score": 110.0,
            "case_results": [
                {
                    "status": "ok",
                    "case_file": "case.txt",
                    "elapsed_ms": 12,
                    "validity": True,
                    "errors": [],
                    "total_score": 110.0,
                    "assigned_count": 1,
                    "unassigned_count": 1,
                    "unassigned_penalty": 100,
                    "detail": [
                        {
                            "task_id_list": "T0001,T0002",
                            "couriers": ["C001", "C002"],
                            "p_complete": 1.0,
                            "expected_score": 10.0,
                            "cost": 10.0,
                        }
                    ],
                    "total_tasks": 3,
                    "total_couriers": 4,
                }
            ],
        }

        case_rows = eval_report.build_case_rows(payload)
        task_rows = eval_report.build_task_rows(payload)

        self.assertEqual(case_rows[0]["case_index"], 1)
        self.assertEqual(case_rows[0]["case_file"], "case.txt")
        self.assertEqual(case_rows[0]["covered_task_count"], 2)
        self.assertEqual(case_rows[0]["recomputed_total_score"], 110.0)
        self.assertEqual(task_rows[0]["task_ids"], "T0001,T0002")
        self.assertEqual(task_rows[0]["task_count"], 2)
        self.assertEqual(task_rows[0]["couriers"], "C001,C002")
        self.assertEqual(task_rows[0]["courier_count"], 2)

    def test_save_result_outputs_uses_jobid_subdirectory_with_fixed_filenames(self):
        payload = {
            "job_id": "job-1",
            "avg_score": 10.0,
            "case_results": [
                {
                    "status": "ok",
                    "case_file": "case.txt",
                    "validity": True,
                    "total_score": 10.0,
                    "unassigned_count": 0,
                    "unassigned_penalty": 0,
                    "detail": [
                        {
                            "task_id_list": "T0001",
                            "couriers": ["C001"],
                            "p_complete": 1.0,
                            "expected_score": 10.0,
                            "cost": 10.0,
                        }
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            outputs = eval_report.save_result_outputs(payload, Path(tmp), "job-1")

            self.assertEqual(outputs["json_path"], Path(tmp) / "job-1" / "response.json")
            self.assertEqual(outputs["cases_path"], Path(tmp) / "job-1" / "cases.csv")
            self.assertEqual(outputs["tasks_path"], Path(tmp) / "job-1" / "tasks.csv")
            self.assertTrue(outputs["json_path"].exists())
            self.assertTrue(outputs["cases_path"].exists())
            self.assertTrue(outputs["tasks_path"].exists())


if __name__ == "__main__":
    unittest.main()
