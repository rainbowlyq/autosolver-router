import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen


LEADERBOARD_URL = "https://hackathon.mykeeta.com/leaderboard?detail=1"
DEFAULT_TOKEN = "13900139005"

TEAM_COLUMNS = (
    "rank",
    "team",
    "best_score",
    "submissions",
    "last_time",
)

SUBMISSION_COLUMNS = (
    "team",
    "team_rank",
    "submission_index",
    "time",
    "avg_score",
    "case_count",
    "success_count",
)

CASE_COLUMNS = (
    "team",
    "team_rank",
    "submission_index",
    "submission_time",
    "case_file",
    "status",
    "score",
    "assigned",
    "total_tasks",
    "elapsed_ms",
)


def build_team_rows(leaderboard):
    return [
        {
            "rank": entry.get("rank", ""),
            "team": entry.get("team", ""),
            "best_score": entry.get("best_score", ""),
            "submissions": entry.get("submissions", ""),
            "last_time": entry.get("last_time", ""),
        }
        for entry in leaderboard
    ]


def build_submission_rows(leaderboard):
    rows = []
    for entry in leaderboard:
        team = entry.get("team", "")
        rank = entry.get("rank", "")
        for idx, hist in enumerate(entry.get("history", []), 1):
            rows.append(
                {
                    "team": team,
                    "team_rank": rank,
                    "submission_index": idx,
                    "time": hist.get("time", ""),
                    "avg_score": hist.get("avg_score", ""),
                    "case_count": hist.get("case_count", ""),
                    "success_count": hist.get("success_count", ""),
                }
            )
    return rows


def build_case_rows(leaderboard):
    rows = []
    for entry in leaderboard:
        team = entry.get("team", "")
        rank = entry.get("rank", "")
        for idx, hist in enumerate(entry.get("history", []), 1):
            sub_time = hist.get("time", "")
            for case in hist.get("case_results", []):
                rows.append(
                    {
                        "team": team,
                        "team_rank": rank,
                        "submission_index": idx,
                        "submission_time": sub_time,
                        "case_file": case.get("case_file", ""),
                        "status": case.get("status", ""),
                        "score": case.get("score", ""),
                        "assigned": case.get("assigned", ""),
                        "total_tasks": case.get("total_tasks", ""),
                        "elapsed_ms": case.get("elapsed_ms", ""),
                    }
                )
    return rows


def fetch_payload(url=LEADERBOARD_URL, token=DEFAULT_TOKEN, timeout=30.0):
    headers = {
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
        "Referer": "https://hackathon.mykeeta.com/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "X-Token": token,
        "sec-ch-ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }
    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return json.loads(resp.read().decode(charset))


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def save_outputs(payload, output_dir):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(output_dir) / ts

    leaderboard = payload.get("leaderboard", [])
    team_rows = build_team_rows(leaderboard)
    submission_rows = build_submission_rows(leaderboard)
    case_rows = build_case_rows(leaderboard)

    paths = {
        "json_path": out / "response.json",
        "teams_path": out / "teams.csv",
        "submissions_path": out / "submissions.csv",
        "cases_path": out / "cases.csv",
    }

    out.mkdir(parents=True, exist_ok=True)
    paths["json_path"].write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_csv(paths["teams_path"], TEAM_COLUMNS, team_rows)
    write_csv(paths["submissions_path"], SUBMISSION_COLUMNS, submission_rows)
    write_csv(paths["cases_path"], CASE_COLUMNS, case_rows)

    return paths


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch and save hackathon leaderboard data.")
    parser.add_argument("--token", default=DEFAULT_TOKEN, help="X-Token auth value")
    parser.add_argument("--url", default=LEADERBOARD_URL, help="Leaderboard API URL")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--input-json", type=Path, help="parse local response JSON instead of fetching")
    parser.add_argument("--output-dir", type=Path, default=Path("results/leaderboard"))
    return parser.parse_args()


def main():
    args = parse_args()
    if args.input_json:
        payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    else:
        payload = fetch_payload(args.url, args.token, args.timeout)

    outputs = save_outputs(payload, args.output_dir)

    leaderboard = payload.get("leaderboard", [])
    total_submissions = sum(e.get("submissions", 0) for e in leaderboard)
    total_cases = sum(
        len(c)
        for e in leaderboard
        for h in e.get("history", [])
        for c in [h.get("case_results", [])]
    )

    print("JSON: {0}".format(outputs["json_path"]))
    print("队伍表: {0}".format(outputs["teams_path"]))
    print("提交表: {0}".format(outputs["submissions_path"]))
    print("用例表: {0}".format(outputs["cases_path"]))
    print("队伍数: {0}".format(len(leaderboard)))
    print("提交数: {0}".format(total_submissions))
    print("用例记录数: {0}".format(total_cases))


if __name__ == "__main__":
    main()
