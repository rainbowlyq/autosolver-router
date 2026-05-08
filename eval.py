import argparse
import csv
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


BASE_URL = "https://hackathon.mykeeta.com/result"
PENALTY = 100.0
CASE_COLUMNS = (
    "case_index",
    "case_file",
    "status",
    "validity",
    "elapsed_ms",
    "total_score",
    "recomputed_total_score",
    "score_delta",
    "assigned_count",
    "detail_count",
    "covered_task_count",
    "unassigned_count",
    "unassigned_penalty",
    "total_tasks",
    "total_couriers",
    "mean_p_complete",
    "mean_expected_score",
    "mean_cost",
    "errors",
)
TASK_COLUMNS = (
    "case_index",
    "case_file",
    "row_index",
    "task_id_list",
    "task_ids",
    "task_count",
    "couriers",
    "courier_count",
    "p_complete",
    "expected_score",
    "cost",
    "recomputed_cost",
    "cost_delta",
)


def num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def round4(value):
    return round(float(value), 4)


def task_ids(task_id_list):
    return [part.strip() for part in str(task_id_list or "").split(",") if part.strip()]


def recompute_detail_cost(detail):
    p = num(detail.get("p_complete"))
    return p * num(detail.get("expected_score")) + (1.0 - p) * PENALTY


def build_case_rows(payload):
    rows = []
    for case_index, case in enumerate(payload.get("case_results") or [], 1):
        details = case.get("detail") or []
        costs = [num(d.get("cost")) for d in details]
        tasks = set()
        p_values, expected_scores = [], []
        for detail in details:
            tasks.update(task_ids(detail.get("task_id_list")))
            p_values.append(num(detail.get("p_complete")))
            expected_scores.append(num(detail.get("expected_score")))

        recomputed_total = round4(sum(costs) + int(num(case.get("unassigned_count"))) * PENALTY)
        total_score = num(case.get("total_score"))
        rows.append(
            {
                "case_index": case_index,
                "case_file": case.get("case_file", ""),
                "status": case.get("status", ""),
                "validity": case.get("validity", ""),
                "elapsed_ms": case.get("elapsed_ms", ""),
                "total_score": total_score,
                "recomputed_total_score": recomputed_total,
                "score_delta": round(total_score - recomputed_total, 8),
                "assigned_count": case.get("assigned_count", ""),
                "detail_count": len(details),
                "covered_task_count": len(tasks),
                "unassigned_count": case.get("unassigned_count", ""),
                "unassigned_penalty": case.get("unassigned_penalty", ""),
                "total_tasks": case.get("total_tasks", ""),
                "total_couriers": case.get("total_couriers", ""),
                "mean_p_complete": round4(sum(p_values) / len(p_values)) if p_values else 0.0,
                "mean_expected_score": round4(sum(expected_scores) / len(expected_scores))
                if expected_scores
                else 0.0,
                "mean_cost": round4(sum(costs) / len(costs)) if costs else 0.0,
                "errors": "; ".join(str(e) for e in case.get("errors", [])),
            }
        )
    return rows


def build_task_rows(payload):
    rows = []
    for case_index, case in enumerate(payload.get("case_results") or [], 1):
        for row_index, detail in enumerate(case.get("detail") or [], 1):
            tasks = task_ids(detail.get("task_id_list"))
            couriers = detail.get("couriers") or []
            recomputed_cost = round4(recompute_detail_cost(detail))
            cost = num(detail.get("cost"))
            rows.append(
                {
                    "case_index": case_index,
                    "case_file": case.get("case_file", ""),
                    "row_index": row_index,
                    "task_id_list": detail.get("task_id_list", ""),
                    "task_ids": ",".join(tasks),
                    "task_count": len(tasks),
                    "couriers": ",".join(str(c) for c in couriers),
                    "courier_count": len(couriers),
                    "p_complete": num(detail.get("p_complete")),
                    "expected_score": num(detail.get("expected_score")),
                    "cost": cost,
                    "recomputed_cost": recomputed_cost,
                    "cost_delta": round(cost - recomputed_cost, 8),
                }
            )
    return rows


def analyze_result_payload(payload, tolerance=0.001):
    cases, tasks = build_case_rows(payload), build_task_rows(payload)
    scores = [num(row["total_score"]) for row in cases]
    recomputed_avg = round4(sum(scores) / len(scores)) if scores else 0.0
    reported_avg = num(payload.get("avg_score"))
    max_detail_delta = max([abs(num(row["cost_delta"])) for row in tasks] or [0.0])
    max_case_delta = max([abs(num(row["score_delta"])) for row in cases] or [0.0])
    avg_delta = round(reported_avg - recomputed_avg, 8)
    return {
        "formula": "cost=p_complete*expected_score+(1-p_complete)*100; total_score=sum(cost)+unassigned_count*100; avg_score=mean(total_score)",
        "formula_matches": max_detail_delta <= tolerance
        and max_case_delta <= tolerance
        and abs(avg_delta) <= tolerance,
        "case_count": len(cases),
        "success_count": payload.get("success_count", 0),
        "reported_avg_score": reported_avg,
        "recomputed_avg_score": recomputed_avg,
        "avg_score_delta": avg_delta,
        "max_detail_cost_delta": max_detail_delta,
        "max_case_score_delta": max_case_delta,
        "case_rows": cases,
        "task_rows": tasks,
    }


def fetch_payload(jobid, base_url=BASE_URL, timeout=30.0):
    url = base_url.format(jobid=quote(jobid, safe="")) if "{jobid}" in base_url else base_url.rstrip("/") + "/" + quote(jobid, safe="")
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "autosolver-eval/1.0"})
    with urlopen(req, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset))


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def save_result_outputs(payload, output_dir=Path("results"), jobid=None):
    jobid = str(jobid or payload.get("job_id") or "result")
    out = Path(output_dir) / jobid
    analysis = analyze_result_payload(payload)
    paths = {
        "json_path": out / "response.json",
        "cases_path": out / "cases.csv",
        "tasks_path": out / "tasks.csv",
        "analysis": analysis,
    }
    out.mkdir(parents=True, exist_ok=True)
    paths["json_path"].write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(paths["cases_path"], CASE_COLUMNS, analysis["case_rows"])
    write_csv(paths["tasks_path"], TASK_COLUMNS, analysis["task_rows"])
    return paths


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch and parse hackathon result JSON.")
    parser.add_argument("jobid", nargs="?", help="job id for /result/{jobid}")
    parser.add_argument("--input-json", type=Path, help="parse local response JSON instead of fetching")
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.jobid and not args.input_json:
        raise SystemExit("请传入 jobid，或使用 --input-json 解析本地 JSON。")
    payload = json.loads(args.input_json.read_text(encoding="utf-8")) if args.input_json else fetch_payload(args.jobid, args.base_url, args.timeout)
    outputs = save_result_outputs(payload, args.output_dir, args.jobid or payload.get("job_id") or args.input_json.stem)
    analysis = outputs["analysis"]
    print("JSON: {0}".format(outputs["json_path"]))
    print("算例表: {0}".format(outputs["cases_path"]))
    print("任务表: {0}".format(outputs["tasks_path"]))
    print("评分公式: {0}".format(analysis["formula"]))
    print("公式校验: {0}".format("匹配" if analysis["formula_matches"] else "未完全匹配"))
    print("avg_score: {0} / recomputed {1}".format(analysis["reported_avg_score"], analysis["recomputed_avg_score"]))
    print("max_detail_cost_delta: {0}".format(analysis["max_detail_cost_delta"]))
    print("max_case_score_delta: {0}".format(analysis["max_case_score_delta"]))


if __name__ == "__main__":
    main()
