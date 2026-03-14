#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from compare_results import compare_result_dirs

REPO_ROOT = Path("/home/xin/River_net_parallel")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = PROJECT_ROOT / "reports"
BENCH_REPORT_ROOT = REPORT_ROOT / "benchmark_runs"
REAL_DIR = REPO_ROOT / "handoff_network_model_20260312" / "result" / "Islam_real_data"
ACCEPTED_EXACT_10M = REPO_ROOT / "handoff_network_model_20260312" / "result" / "tmp_optghr_process_fork_10m"
ACCEPTED_EXACT_40H = REPO_ROOT / "handoff_network_model_20260312" / "result" / "exp_optghr_process_auto_py311_40h"

CONTROL_POINT_SPECS = [
    ("node11_level", "level", 0),
    ("node11_Q", "Q", 0),
    ("node12_level", "level", 11),
    ("node12_Q", "Q", 11),
]

PRESETS = {
    "exact_10m": {
        "label": "exact_10m",
        "worktree": Path("/tmp/overnight_exact_baseline_clean/handoff_network_model_20260312"),
        "output_path": "result/overnight_exact_10m",
        "baseline_dir": ACCEPTED_EXACT_10M,
        "sim_end_time": "2024-01-01 00:10:00",
        "env": {
            "MPLCONFIGDIR": "/tmp/mplconfig",
            "ISLAM_OUTPUT_RIVERS": "river11",
            "ISLAM_USE_FINE_INTERPOLATION": "0",
            "ISLAM_USE_PARALLEL": "1",
            "ISLAM_PARALLEL_BACKEND": "process",
            "ISLAM_PARALLEL_START_METHOD": "fork",
            "ISLAM_N_WORKERS": "4",
            "ISLAM_SAVE_RUN_SUMMARY": "1",
            "ISLAM_SAVE_CFL_HISTORY": "0",
        },
    },
    "exact_40h": {
        "label": "exact_40h",
        "worktree": Path("/tmp/overnight_exact_baseline_clean/handoff_network_model_20260312"),
        "output_path": "result/overnight_exact_40h",
        "baseline_dir": ACCEPTED_EXACT_40H,
        "sim_end_time": "2024-01-02 16:00:00",
        "env": {
            "MPLCONFIGDIR": "/tmp/mplconfig",
            "ISLAM_OUTPUT_RIVERS": "river11",
            "ISLAM_USE_FINE_INTERPOLATION": "0",
            "ISLAM_USE_PARALLEL": "1",
            "ISLAM_PARALLEL_BACKEND": "process",
            "ISLAM_PARALLEL_START_METHOD": "fork",
            "ISLAM_N_WORKERS": "4",
            "ISLAM_SAVE_RUN_SUMMARY": "1",
            "ISLAM_SAVE_CFL_HISTORY": "0",
        },
    },
}


def parse_model_runtime(stdout_text: str):
    step_match = re.search(r"共计算\s*(\d+)\s*步", stdout_text)
    time_match = re.search(r"总耗时:\s*([0-9.]+)\s*秒", stdout_text)
    return {
        "step_count": int(step_match.group(1)) if step_match else None,
        "model_time_s": float(time_match.group(1)) if time_match else None,
    }


def read_run_summary(result_dir: Path):
    path = result_dir / "run_summary.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def summary_model_time(summary):
    if summary is None:
        return None
    return summary.get("model_time_s", summary.get("calculation_time"))


def summary_step_count(summary):
    if summary is None:
        return None
    return summary.get("step_count")


def summary_relative_volume_change(summary):
    if summary is None:
        return None
    return summary.get("relative_volume_change", summary.get("network_relative_volume_change"))


def summary_final_volume(summary):
    if summary is None:
        return None
    return summary.get("final_total_volume", summary.get("network_total_volume_final"))


def summary_rivers(summary):
    if summary is None:
        return []
    return summary.get("per_river", summary.get("rivers", []))


def detect_flow_sign(ds: xr.Dataset, indices=(0, 11)):
    blocks = [np.asarray(ds["Q"].isel(space=idx).to_numpy(), dtype=float) for idx in indices]
    q_all = np.concatenate(blocks)
    return 1 if float(np.nanmean(q_all)) >= 0.0 else -1


def load_control_series(result_dir: Path):
    ds = xr.open_dataset(result_dir / "river11_interpolated_output.nc", engine="h5netcdf")
    time_h = np.asarray(ds["time"].to_numpy(), dtype=float) / 3600.0
    flow_sign = detect_flow_sign(ds)
    series = {}
    for name, var, idx in CONTROL_POINT_SPECS:
        values = np.asarray(ds[var].isel(space=idx).to_numpy(), dtype=float)
        if var == "Q":
            values = flow_sign * values
        series[name] = {
            "time_h": time_h,
            "values": values,
        }
    return series


def compute_nse(obs, sim):
    obs = np.asarray(obs, dtype=float)
    sim = np.asarray(sim, dtype=float)
    den = np.sum((obs - np.mean(obs)) ** 2)
    if den <= 0.0:
        return np.nan
    return 1.0 - np.sum((sim - obs) ** 2) / den


def load_real_series(series_name: str):
    path = REAL_DIR / f"{series_name}.csv"
    df = pd.read_csv(path)
    df.columns = [c.strip().replace("\ufeff", "").lower() for c in df.columns]
    return df.sort_values("x").reset_index(drop=True)


def compute_observed_metrics(result_dir: Path):
    sim_series = load_control_series(result_dir)
    per_series = {}
    for series_name, payload in sim_series.items():
        real_df = load_real_series(series_name)
        sim_on_real = np.interp(real_df["x"].to_numpy(), payload["time_h"], payload["values"])
        diff = sim_on_real - real_df["y"].to_numpy()
        per_series[series_name] = {
            "nse": float(compute_nse(real_df["y"].to_numpy(), sim_on_real)),
            "rmse": float(np.sqrt(np.mean(diff * diff))),
            "bias": float(np.mean(diff)),
        }
    mean_nse = float(np.nanmean([v["nse"] for v in per_series.values()]))
    return {"mean_nse": mean_nse, "per_series": per_series}


def compute_pair_metrics(reference_dir: Path, candidate_dir: Path):
    ref_series = load_control_series(reference_dir)
    cand_series = load_control_series(candidate_dir)
    per_series = {}
    max_abs_overall = 0.0
    max_peak_error = 0.0
    max_arrival_time_error_h = 0.0
    for series_name in ref_series:
        ref_time = ref_series[series_name]["time_h"]
        cand_time = cand_series[series_name]["time_h"]
        if ref_time.shape != cand_time.shape or not np.allclose(ref_time, cand_time):
            cand_values = np.interp(ref_time, cand_time, cand_series[series_name]["values"])
            time_axis = ref_time
        else:
            cand_values = cand_series[series_name]["values"]
            time_axis = ref_time
        ref_values = ref_series[series_name]["values"]
        diff = np.abs(cand_values - ref_values)
        max_abs = float(diff.max())
        peak_ref_idx = int(np.nanargmax(ref_values))
        peak_cand_idx = int(np.nanargmax(cand_values))
        peak_error = float(abs(cand_values[peak_cand_idx] - ref_values[peak_ref_idx]))
        arrival_error_h = float(abs(time_axis[peak_cand_idx] - time_axis[peak_ref_idx]))
        max_abs_overall = max(max_abs_overall, max_abs)
        max_peak_error = max(max_peak_error, peak_error)
        max_arrival_time_error_h = max(max_arrival_time_error_h, arrival_error_h)
        per_series[series_name] = {
            "max_abs": max_abs,
            "mean_abs": float(diff.mean()),
            "rmse": float(np.sqrt(np.mean(diff * diff))),
            "peak_error": peak_error,
            "arrival_time_error_h": arrival_error_h,
            "ref_peak_value": float(ref_values[peak_ref_idx]),
            "cand_peak_value": float(cand_values[peak_cand_idx]),
        }

    ref_summary = read_run_summary(reference_dir)
    cand_summary = read_run_summary(candidate_dir)
    volume = {
        "available": False,
        "reference_summary_source": None,
        "abs_relative_volume_change_error": None,
        "final_volume_abs_diff": None,
    }
    if ref_summary and cand_summary:
        volume = {
            "available": True,
            "reference_summary_source": str(reference_dir / "run_summary.json"),
            "abs_relative_volume_change_error": float(
                abs(
                    float(summary_relative_volume_change(cand_summary))
                    - float(summary_relative_volume_change(ref_summary))
                )
            ),
            "final_volume_abs_diff": float(
                abs(float(summary_final_volume(cand_summary)) - float(summary_final_volume(ref_summary)))
            ),
        }

    return {
        "per_series": per_series,
        "max_abs_overall": max_abs_overall,
        "max_peak_error_overall": max_peak_error,
        "max_arrival_time_error_h_overall": max_arrival_time_error_h,
        "volume": volume,
    }


def as_markdown_table(rows):
    headers = list(rows[0].keys()) if rows else []
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(row[h]) for h in headers) + " |")
    return "\n".join(out)


def write_evaluation(report_path: Path, payload: dict):
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path = report_path.with_suffix(".md")
    compare = payload.get("compare", {})
    observed = payload.get("observed_vs_real", {})
    pair = payload.get("candidate_vs_reference", {})
    rows = []
    for name, metrics in observed.get("per_series", {}).items():
        pair_series = pair.get("per_series", {}).get(name, {})
        rows.append(
            {
                "series": name,
                "nse": f"{metrics['nse']:.6f}",
                "max_abs": f"{pair_series.get('max_abs', float('nan')):.6g}",
                "peak_error": f"{pair_series.get('peak_error', float('nan')):.6g}",
                "arrival_time_error_h": f"{pair_series.get('arrival_time_error_h', float('nan')):.6g}",
            }
        )
    lines = [
        f"# {payload['label']}",
        "",
        f"- candidate_dir: `{payload['candidate_dir']}`",
        f"- reference_dir: `{payload['reference_dir']}`",
        f"- fresh_run: `{payload['fresh_run']}`",
        f"- wall_time_s: `{payload.get('wall_time_s')}`",
        f"- model_time_s: `{payload.get('model_time_s')}`",
        f"- step_count: `{payload.get('step_count')}`",
        f"- allclose: `{compare.get('allclose')}`",
        f"- mean_nse: `{observed.get('mean_nse')}`",
        f"- max_abs_overall: `{pair.get('max_abs_overall')}`",
        f"- max_peak_error_overall: `{pair.get('max_peak_error_overall')}`",
        f"- max_arrival_time_error_h_overall: `{pair.get('max_arrival_time_error_h_overall')}`",
        f"- volume_error_available: `{pair.get('volume', {}).get('available')}`",
        f"- abs_relative_volume_change_error: `{pair.get('volume', {}).get('abs_relative_volume_change_error')}`",
        "",
        "## Per-Series",
        "",
        as_markdown_table(rows) if rows else "_no series_",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_benchmark_matrix():
    rows = []
    for json_path in sorted(BENCH_REPORT_ROOT.glob("*.json")):
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        if "fresh_run" not in payload or "compare" not in payload:
            continue
        compare = payload.get("compare", {})
        observed = payload.get("observed_vs_real", {})
        pair = payload.get("candidate_vs_reference", {})
        rows.append(
            {
                "label": payload["label"],
                "fresh_run": payload["fresh_run"],
                "wall_time_s": payload.get("wall_time_s"),
                "model_time_s": payload.get("model_time_s"),
                "step_count": payload.get("step_count"),
                "allclose": compare.get("allclose"),
                "mean_nse": observed.get("mean_nse"),
                "max_abs_overall": pair.get("max_abs_overall"),
                "max_peak_error_overall": pair.get("max_peak_error_overall"),
                "max_arrival_time_error_h_overall": pair.get("max_arrival_time_error_h_overall"),
                "abs_relative_volume_change_error": pair.get("volume", {}).get("abs_relative_volume_change_error"),
                "candidate_dir": payload["candidate_dir"],
                "reference_dir": payload["reference_dir"],
            }
        )
    md_path = REPORT_ROOT / "benchmark_matrix.md"
    lines = [
        "# Benchmark Matrix",
        "",
        "This matrix is generated by `tools/overnight_benchmark.py`.",
        "",
    ]
    if rows:
        lines.append(as_markdown_table(rows))
    else:
        lines.append("_no benchmark rows_")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def evaluate_candidate(label: str, candidate_dir: Path, reference_dir: Path, fresh_run: bool, wall_time_s=None, model_time_s=None, step_count=None):
    compare = compare_result_dirs(reference_dir, candidate_dir, rtol=1e-12, atol=1e-12)
    observed = compute_observed_metrics(candidate_dir)
    pair = compute_pair_metrics(reference_dir, candidate_dir)
    if not pair["volume"]["available"] and compare.get("allclose") and read_run_summary(candidate_dir):
        pair["volume"] = {
            "available": True,
            "reference_summary_source": "candidate_proxy_due_to_exact_allclose",
            "abs_relative_volume_change_error": 0.0,
            "final_volume_abs_diff": 0.0,
        }
    payload = {
        "label": label,
        "fresh_run": fresh_run,
        "candidate_dir": str(candidate_dir.resolve()),
        "reference_dir": str(reference_dir.resolve()),
        "wall_time_s": wall_time_s,
        "model_time_s": model_time_s,
        "step_count": step_count,
        "compare": compare,
        "observed_vs_real": observed,
        "candidate_vs_reference": pair,
    }
    BENCH_REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    report_path = BENCH_REPORT_ROOT / f"{label}.json"
    write_evaluation(report_path, payload)
    update_benchmark_matrix()
    return report_path, payload


def run_preset(name: str):
    cfg = PRESETS[name]
    worktree = cfg["worktree"]
    env = os.environ.copy()
    env.update(cfg["env"])
    env["ISLAM_OUTPUT_PATH"] = cfg["output_path"]
    env["ISLAM_SIM_END_TIME"] = cfg["sim_end_time"]

    cmd = ["conda", "run", "-n", "python311", "python", "Islam.py"]
    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=worktree,
        env=env,
        capture_output=True,
        text=True,
    )
    wall_time_s = time.perf_counter() - t0
    stdout = proc.stdout
    stderr = proc.stderr
    BENCH_REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    log_base = BENCH_REPORT_ROOT / name
    (log_base.with_suffix(".stdout.log")).write_text(stdout, encoding="utf-8")
    (log_base.with_suffix(".stderr.log")).write_text(stderr, encoding="utf-8")
    if proc.returncode != 0:
        raise SystemExit(
            f"{name} failed with exit code {proc.returncode}\nstdout:\n{stdout}\nstderr:\n{stderr}"
        )
    runtime = parse_model_runtime(stdout)
    candidate_dir = worktree / cfg["output_path"]
    summary = read_run_summary(candidate_dir)
    report_path, _ = evaluate_candidate(
        label=name,
        candidate_dir=candidate_dir,
        reference_dir=cfg["baseline_dir"],
        fresh_run=True,
        wall_time_s=round(wall_time_s, 6),
        model_time_s=summary_model_time(summary) if summary_model_time(summary) is not None else runtime["model_time_s"],
        step_count=summary_step_count(summary) if summary_step_count(summary) is not None else runtime["step_count"],
    )
    manifest = {
        "label": name,
        "command": cmd,
        "cwd": str(worktree),
        "env": {
            k: env[k]
            for k in sorted(set(cfg["env"]).union({"ISLAM_OUTPUT_PATH", "ISLAM_SIM_END_TIME"}))
        },
        "candidate_dir": str(candidate_dir.resolve()),
        "reference_dir": str(Path(cfg["baseline_dir"]).resolve()),
        "stdout_log": str(log_base.with_suffix(".stdout.log")),
        "stderr_log": str(log_base.with_suffix(".stderr.log")),
        "evaluation_report": str(report_path),
    }
    (log_base.with_suffix(".manifest.json")).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run-preset")
    p_run.add_argument("name", choices=sorted(PRESETS))

    p_eval = sub.add_parser("evaluate-existing")
    p_eval.add_argument("label")
    p_eval.add_argument("candidate_dir")
    p_eval.add_argument("reference_dir")
    p_eval.add_argument("--wall-time-s", type=float, default=None)
    p_eval.add_argument("--model-time-s", type=float, default=None)
    p_eval.add_argument("--step-count", type=int, default=None)

    sub.add_parser("matrix")

    args = parser.parse_args()
    if args.cmd == "run-preset":
        report_path = run_preset(args.name)
        print(report_path)
    elif args.cmd == "evaluate-existing":
        summary = read_run_summary(Path(args.candidate_dir))
        report_path, _ = evaluate_candidate(
            label=args.label,
            candidate_dir=Path(args.candidate_dir),
            reference_dir=Path(args.reference_dir),
            fresh_run=False,
            wall_time_s=args.wall_time_s,
            model_time_s=args.model_time_s if args.model_time_s is not None else summary_model_time(summary),
            step_count=args.step_count if args.step_count is not None else summary_step_count(summary),
        )
        print(report_path)
    elif args.cmd == "matrix":
        print(update_benchmark_matrix())


if __name__ == "__main__":
    main()
