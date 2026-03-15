#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def load_run_summary(result_dir: Path):
    path = result_dir / "run_summary.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def percentile_safe(values, q):
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return np.nan
    return float(np.nanpercentile(arr, q))


def df_to_markdown(df: pd.DataFrame):
    if df.empty:
        return "_no rows_"
    headers = list(df.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(str(getattr(row, col)) for col in headers) + " |")
    return "\n".join(lines)


def build_markdown(label, result_dir: Path, df: pd.DataFrame, topk_csv: Path):
    used_dt = df["used_dt_s"].to_numpy(dtype=float)
    summary = load_run_summary(result_dir)
    total_steps = int(len(df))
    model_time_s = None if summary is None else summary.get("model_time_s", summary.get("calculation_time"))
    per_step_model_cost = None
    if model_time_s is not None and total_steps > 0:
        per_step_model_cost = float(model_time_s) / total_steps

    category_counts = (
        df["category"].fillna("unknown").value_counts(dropna=False).rename_axis("category").reset_index(name="count")
    )
    schedule_counts = (
        df["schedule_reason"].fillna("unknown").value_counts(dropna=False).rename_axis("schedule_reason").reset_index(name="count")
    )
    min_rows = df.nsmallest(min(10, total_steps), "used_dt_s")[
        ["step", "time_s", "used_dt_s", "schedule_reason", "river_name", "cell_index", "category", "boundary_node"]
    ].copy()
    if not min_rows.empty:
        min_rows["time_h"] = min_rows["time_s"] / 3600.0

    lines = [
        f"# {label}",
        "",
        f"- result_dir: `{result_dir}`",
        f"- total_steps: `{total_steps}`",
        f"- mean_used_dt_s: `{float(np.mean(used_dt)) if total_steps else np.nan}`",
        f"- median_used_dt_s: `{float(np.median(used_dt)) if total_steps else np.nan}`",
        f"- p05_used_dt_s: `{percentile_safe(used_dt, 5)}`",
        f"- p01_used_dt_s: `{percentile_safe(used_dt, 1)}`",
        f"- min_used_dt_s: `{float(np.min(used_dt)) if total_steps else np.nan}`",
        f"- max_used_dt_s: `{float(np.max(used_dt)) if total_steps else np.nan}`",
        f"- model_time_s: `{model_time_s}`",
        f"- model_time_per_step_s: `{per_step_model_cost}`",
        "",
        "## Limiter Category Share",
        "",
    ]
    if not category_counts.empty:
        lines.append(df_to_markdown(category_counts))
    else:
        lines.append("_no category rows_")
    lines.extend(["", "## Schedule Reason Share", ""])
    if not schedule_counts.empty:
        lines.append(df_to_markdown(schedule_counts))
    else:
        lines.append("_no schedule rows_")
    lines.extend(["", "## Smallest Dt Windows", ""])
    if not min_rows.empty:
        lines.append(df_to_markdown(min_rows))
    else:
        lines.append("_no dt rows_")
    lines.extend(
        [
            "",
            "## Top-K Limiter CSV",
            "",
            f"`{topk_csv}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("result_dir")
    parser.add_argument("--label", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--out-topk", required=True)
    parser.add_argument("--topk", type=int, default=25)
    args = parser.parse_args()

    result_dir = Path(args.result_dir)
    df = pd.read_csv(result_dir / "dt_profile.csv")
    df["boundary_node"] = df["boundary_node"].fillna("")
    df["river_name"] = df["river_name"].fillna("")
    df["category"] = df["category"].fillna("unknown")

    topk = (
        df.groupby(["river_name", "cell_index", "boundary_node", "category", "schedule_reason"], dropna=False)
        .agg(
            count=("used_dt_s", "size"),
            mean_used_dt_s=("used_dt_s", "mean"),
            min_used_dt_s=("used_dt_s", "min"),
            median_used_dt_s=("used_dt_s", "median"),
            min_time_s=("time_s", "min"),
            max_time_s=("time_s", "max"),
        )
        .reset_index()
        .sort_values(["count", "min_used_dt_s"], ascending=[False, True])
        .head(args.topk)
    )

    out_topk = Path(args.out_topk)
    out_topk.parent.mkdir(parents=True, exist_ok=True)
    topk.to_csv(out_topk, index=False)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(
        build_markdown(args.label, result_dir, df, out_topk),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
