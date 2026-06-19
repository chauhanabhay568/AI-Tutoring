from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["metric"]].append(row)

    metrics = {}
    for name, metric_rows in grouped.items():
        scored = [row for row in metric_rows if row["score"] is not None]
        passed = sum(row["passed"] is True for row in scored)
        metrics[name] = {
            "evaluated": len(scored),
            "errors": len(metric_rows) - len(scored),
            "mean_score": round(sum(row["score"] for row in scored) / len(scored), 4)
            if scored else None,
            "pass_rate": round(passed / len(scored), 4) if scored else None,
        }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metric_summary": metrics,
    }


def write_reports(rows: list[dict[str, Any]], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output_dir / f"evaluation_results_{timestamp}.csv"
    json_path = output_dir / f"evaluation_summary_{timestamp}.json"

    fields = ["evaluation_type", "case_id", "metric", "score", "threshold", "passed", "reason", "error"]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field) for field in fields} for row in rows)

    payload = summarize(rows)
    payload["result_rows"] = len(rows)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return csv_path, json_path

