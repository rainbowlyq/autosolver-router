import importlib.util
import tempfile
import unittest
from pathlib import Path

from solver import solve as project_solve


SAMPLE_INPUT = "\n".join(
    [
        "task_id_list\tcourier_id\ttotal_score\twillingness",
        "T0001\tC001\t10.0\t0.5",
        "T0002\tC002\t11.0\t0.5",
        "T0001,T0002\tC003\t15.0\t0.9",
    ]
)


def load_module(path):
    spec = importlib.util.spec_from_file_location("packed_solver_for_test", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PackScriptTests(unittest.TestCase):
    def test_pack_generates_single_file_solver_from_template(self):
        from pack import pack_solver

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "solver_packed.py"

            result = pack_solver(output_path=output_path, strip_hints=False)

            generated = output_path.read_text(encoding="utf-8")
            packed_solver = load_module(output_path)
            self.assertEqual(packed_solver.solve(SAMPLE_INPUT), project_solve(SAMPLE_INPUT))
            self.assertIn("# PACK: autosolver/models.py", generated)
            self.assertIn("# PACK: solver.py", generated)
            self.assertNotIn("from autosolver.", generated)
            self.assertFalse(result.strip_hints_applied)

    def test_pack_can_strip_type_hints_without_breaking_solver(self):
        from pack import pack_solver

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "solver_packed.py"

            result = pack_solver(output_path=output_path, strip_hints=True)

            generated = output_path.read_text(encoding="utf-8")
            packed_solver = load_module(output_path)
            self.assertEqual(packed_solver.solve(SAMPLE_INPUT), project_solve(SAMPLE_INPUT))
            self.assertTrue(result.strip_hints_applied, result.strip_hints_error)
            self.assertNotIn("from typing import", generated)
            self.assertNotIn("NamedTuple", generated)
            self.assertNotIn("->", generated)


if __name__ == "__main__":
    unittest.main()
