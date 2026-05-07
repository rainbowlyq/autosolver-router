from typing import Dict, List, Tuple

from autosolver.models import Candidate, ProblemInstance, Solution


def parse_problem(input_text: str) -> ProblemInstance:
    lines = input_text.strip().splitlines()
    start = 1 if lines and lines[0].startswith("task_id_list") else 0
    candidates = []

    row_index = start
    for raw_line in lines[start:]:
        line = raw_line.strip()
        if not line:
            continue
        current_index = row_index
        row_index += 1

        parts = line.split("\t")
        if len(parts) < 4:
            continue

        task_id_list, courier_id, score_text, willingness_text = parts[:4]
        try:
            total_score = float(score_text)
            willingness = float(willingness_text)
        except ValueError:
            continue

        task_ids = tuple(task_id.strip() for task_id in task_id_list.split(",") if task_id.strip())
        if not task_ids:
            continue

        candidates.append(
            Candidate(
                index=current_index,
                task_id_list=task_id_list.strip(),
                task_ids=task_ids,
                courier_id=courier_id.strip(),
                total_score=total_score,
                willingness=willingness,
            )
        )

    return ProblemInstance.from_candidates(tuple(candidates))


def solution_to_output(solution: Solution) -> List[Tuple[str, List[str]]]:
    grouped_rows = {}  # type: Dict[str, List[str]]
    for assignment in solution.assignments:
        grouped_rows.setdefault(assignment.task_id_list, []).extend(assignment.courier_ids)
    return list(grouped_rows.items())


def format_output_rows(output: List[Tuple[str, List[str]]]) -> str:
    return "\n".join(
        f"{task_id_list}\t{','.join(courier_ids)}"
        for task_id_list, courier_ids in output
    )
