#!/usr/bin/env python3
import argparse
import json
import math
import os
import subprocess
import time
from pathlib import Path

from evaluate_fast_mode import (
    compare_control_points,
    compare_internal_node_history,
    compare_nse,
    compare_volume,
    load_optional_summary,
    load_run_summary,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = PROJECT_ROOT / "reports"
SWEEP_RUN_ROOT = REPORT_ROOT / "sweep_runs"
RESULT_ROOT = PROJECT_ROOT / "result"
REAL_DIR = PROJECT_ROOT / "result" / "Islam_real_data"

ACCEPTED_EXACT_DIR = Path(
    "/home/xin/River_net_parallel/handoff_network_model_20260312/result/exp_optghr_process_auto_py311_40h"
)
EXACT_SUMMARY_PROXY = Path(
    "/tmp/overnight_exact_baseline_clean/handoff_network_model_20260312/result/overnight_exact_40h/run_summary.json"
)

SIM_END_TIME = "2024-01-02 16:00:00"
SIM_TOTAL_SECONDS = 40.0 * 3600.0
BASE_ENV = {
    "MPLCONFIGDIR": "/tmp/mplconfig",
    "ISLAM_OUTPUT_RIVERS": "river11",
    "ISLAM_USE_FINE_INTERPOLATION": "0",
    "ISLAM_USE_PARALLEL": "1",
    "ISLAM_PARALLEL_BACKEND": "process",
    "ISLAM_PARALLEL_START_METHOD": "fork",
    "ISLAM_N_WORKERS": "4",
    "ISLAM_FAST_MODE": "1",
    "ISLAM_SAVE_RUN_SUMMARY": "1",
    "ISLAM_SAVE_INTERNAL_NODE_HISTORY": "0",
}


def candidate_result_dir(label: str) -> Path:
    return RESULT_ROOT / f"sweep_{label}"


def result_metrics_payload(label, candidate_dir, wall_time_s=None, model_time_s=None, step_count=None):
    baseline_summary = load_optional_summary(EXACT_SUMMARY_PROXY)
    candidate_summary = load_run_summary(candidate_dir)
    if model_time_s is None and candidate_summary is not None:
        model_time_s = float(candidate_summary.get("calculation_time", math.nan))
    if step_count is None and candidate_summary is not None:
        step_count = int(candidate_summary.get("step_count", 0))
    nse = compare_nse(str(REAL_DIR), ACCEPTED_EXACT_DIR, candidate_dir)
    control = compare_control_points(ACCEPTED_EXACT_DIR, candidate_dir)
    volume = compare_volume(
        ACCEPTED_EXACT_DIR,
        candidate_dir,
        baseline_summary_override=baseline_summary,
        candidate_summary_override=candidate_summary,
    )
    node_hist = compare_internal_node_history(ACCEPTED_EXACT_DIR, candidate_dir)
    max_abs = max(rec["max_abs"] for rec in control.values())
    max_peak = max(abs(rec["peak_value_error"]) for rec in control.values())
    max_arrival = max(abs(rec["peak_arrival_time_error_h"]) for rec in control.values())
    mean_dt_s = float(SIM_TOTAL_SECONDS / step_count) if step_count else None
    return {
        "label": label,
        "candidate_dir": str(candidate_dir),
        "wall_time_s": wall_time_s,
        "model_time_s": model_time_s,
        "step_count": step_count,
        "mean_dt_s": mean_dt_s,
        "nse": nse,
        "control_points": control,
        "volume": volume,
        "internal_node_history": node_hist,
        "max_abs_overall": max_abs,
        "max_peak_error_overall": max_peak,
        "max_arrival_time_error_h_overall": max_arrival,
    }


def write_candidate_report(payload):
    SWEEP_RUN_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = SWEEP_RUN_ROOT / f"{payload['label']}.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path


def load_existing_candidate_report(label):
    path = SWEEP_RUN_ROOT / f"{label}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def fast_tier(payload):
    wall = payload.get("wall_time_s")
    max_abs = payload.get("max_abs_overall")
    if wall is None:
        return "S?"
    if wall < 30.0:
        return "Target"
    if wall < 60.0 and max_abs is not None and max_abs <= 1.0e-1:
        return "B"
    if wall < 120.0 and max_abs is not None and max_abs <= 5.0e-2:
        return "A"
    return "S"


def record_row(payload, source, notes):
    return {
        "label": payload["label"],
        "source": source,
        "tier": fast_tier(payload),
        "wall_time_s": payload.get("wall_time_s"),
        "model_time_s": payload.get("model_time_s"),
        "step_count": payload.get("step_count"),
        "mean_dt_s": payload.get("mean_dt_s"),
        "mean_nse": payload["nse"]["candidate_mean_nse"],
        "mean_nse_delta": payload["nse"]["mean_nse_delta"],
        "max_abs_overall": payload["max_abs_overall"],
        "max_peak_error_overall": payload["max_peak_error_overall"],
        "max_arrival_time_error_h_overall": payload["max_arrival_time_error_h_overall"],
        "volume_error": (
            None if not payload["volume"]["available"] else payload["volume"]["network_relative_volume_change_delta"]
        ),
        "notes": notes,
    }


def as_markdown_table(rows):
    if not rows:
        return "_no rows_"
    headers = list(rows[0].keys())
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(h)) for h in headers) + " |")
    return "\n".join(lines)


def pareto_front(rows):
    front = []
    for row in rows:
        row_wall = float("inf") if row["wall_time_s"] is None else row["wall_time_s"]
        row_abs = float("inf") if row["max_abs_overall"] is None else row["max_abs_overall"]
        dominated = False
        for other in rows:
            if other is row:
                continue
            other_wall = float("inf") if other["wall_time_s"] is None else other["wall_time_s"]
            other_abs = float("inf") if other["max_abs_overall"] is None else other["max_abs_overall"]
            better_or_equal = (
                other_wall <= row_wall
                and other_abs <= row_abs
            )
            strictly_better = (
                other_wall < row_wall
                or other_abs < row_abs
            )
            if better_or_equal and strictly_better:
                dominated = True
                break
        if not dominated:
            front.append(row)
    return sorted(
        front,
        key=lambda r: (
            float("inf") if r["wall_time_s"] is None else r["wall_time_s"],
            float("inf") if r["max_abs_overall"] is None else r["max_abs_overall"],
        ),
    )


def build_existing_candidates():
    return [
        {
            "label": "fast_40h_iter5_nocfl",
            "kind": "existing",
            "candidate_dir": Path("/home/xin/River_net_parallel/handoff_network_model_20260312/result/exp_fastmode_iter5_nocfl_py311_40h"),
            "wall_time_s": 247.38,
            "model_time_s": 244.39729833602905,
            "step_count": 35874,
            "notes": "legacy FAST baseline without CFL boost",
        },
        {
            "label": "fast_40h_iter5_cfl125",
            "kind": "existing",
            "candidate_dir": Path("/home/xin/River_net_parallel/handoff_network_model_20260312/result/exp_fastmode_iter5_cfl125_py311_40h"),
            "wall_time_s": 195.54,
            "model_time_s": 192.66340517997742,
            "step_count": 28329,
            "notes": "legacy FAST baseline with CFL boost",
        },
        {
            "label": "fast_40h_adaptive",
            "kind": "existing",
            "candidate_dir": RESULT_ROOT / "exp_fastmode_adaptive_py311_40h",
            "wall_time_s": 242.30,
            "model_time_s": 235.27873492240906,
            "step_count": 29989,
            "notes": "adaptive gate only; no extra CFL boost",
        },
        {
            "label": "fast_40h_adaptive_cfl125",
            "kind": "existing",
            "candidate_dir": RESULT_ROOT / "exp_fastmode_adaptive_cfl125_py311_40h",
            "wall_time_s": 193.09,
            "model_time_s": 186.73348426818848,
            "step_count": 23895,
            "notes": "current best FAST candidate before further sweep",
        },
    ]


def build_sweep_candidates():
    candidates = []
    grids = [
        {"solver": "response_corrector", "max_iter": 2, "cfl_scale": 1.50, "dt_factor": 1.20, "adaptive": 0},
        {"solver": "response_corrector", "max_iter": 2, "cfl_scale": 1.75, "dt_factor": 1.25, "adaptive": 0},
        {"solver": "response_root", "max_iter": 2, "cfl_scale": 1.50, "dt_factor": 1.20, "adaptive": 0},
        {"solver": "response_root", "max_iter": 2, "cfl_scale": 1.75, "dt_factor": 1.25, "adaptive": 0},
        {"solver": "response_corrector", "max_iter": 2, "cfl_scale": 2.00, "dt_factor": 1.35, "adaptive": 0},
        {"solver": "response_root", "max_iter": 2, "cfl_scale": 2.00, "dt_factor": 1.35, "adaptive": 0},
        {"solver": "response_corrector", "max_iter": 2, "cfl_scale": 2.25, "dt_factor": 1.50, "adaptive": 0},
        {"solver": "response_root", "max_iter": 2, "cfl_scale": 2.25, "dt_factor": 1.50, "adaptive": 0},
        {"solver": "response_corrector", "max_iter": 3, "cfl_scale": 1.50, "dt_factor": 1.20, "adaptive": 1},
        {"solver": "response_corrector", "max_iter": 3, "cfl_scale": 1.75, "dt_factor": 1.25, "adaptive": 1},
        {"solver": "response_root", "max_iter": 3, "cfl_scale": 1.50, "dt_factor": 1.20, "adaptive": 1},
        {"solver": "response_root", "max_iter": 3, "cfl_scale": 1.75, "dt_factor": 1.25, "adaptive": 1},
        {"solver": "response_root", "max_iter": 2, "cfl_scale": 2.00, "dt_factor": 1.35, "adaptive": 0, "refresh_every": 2, "refresh_mode": "predict"},
        {"solver": "response_root", "max_iter": 2, "cfl_scale": 2.00, "dt_factor": 1.35, "adaptive": 0, "refresh_every": 3, "refresh_mode": "predict"},
        {"solver": "response_root", "max_iter": 2, "cfl_scale": 2.00, "dt_factor": 1.35, "adaptive": 0, "refresh_every": 2, "refresh_mode": "hold"},
        {"solver": "response_root", "max_iter": 2, "cfl_scale": 2.00, "dt_factor": 1.35, "adaptive": 0, "refresh_every": 3, "refresh_mode": "hold"},
        {"solver": "response_root", "max_iter": 2, "cfl_scale": 2.00, "dt_factor": 1.35, "adaptive": 0, "refresh_every": 5, "refresh_mode": "hold"},
        {"solver": "response_root", "max_iter": 2, "cfl_scale": 2.25, "dt_factor": 1.50, "adaptive": 0, "refresh_every": 2, "refresh_mode": "predict"},
        {"solver": "response_root", "max_iter": 2, "cfl_scale": 2.25, "dt_factor": 1.50, "adaptive": 0, "refresh_every": 3, "refresh_mode": "predict"},
        {"solver": "response_root", "max_iter": 2, "cfl_scale": 2.25, "dt_factor": 1.50, "adaptive": 0, "refresh_every": 2, "refresh_mode": "hold"},
        {"solver": "response_root", "max_iter": 2, "cfl_scale": 2.25, "dt_factor": 1.50, "adaptive": 0, "refresh_every": 3, "refresh_mode": "hold"},
        {"solver": "response_root", "max_iter": 2, "cfl_scale": 2.25, "dt_factor": 1.50, "adaptive": 0, "refresh_every": 5, "refresh_mode": "hold"},
        {"solver": "response_root", "max_iter": 2, "cfl_scale": 2.50, "dt_factor": 1.65, "adaptive": 0, "refresh_every": 2, "refresh_mode": "predict"},
        {"solver": "response_root", "max_iter": 2, "cfl_scale": 2.50, "dt_factor": 1.65, "adaptive": 0, "refresh_every": 3, "refresh_mode": "hold"},
        {"solver": "response_root", "max_iter": 2, "cfl_scale": 3.00, "dt_factor": 2.00, "adaptive": 0, "refresh_every": 3, "refresh_mode": "hold"},
    ]
    for cfg in grids:
        solver = cfg["solver"]
        max_iter = cfg["max_iter"]
        cfl_scale = cfg["cfl_scale"]
        dt_factor = cfg["dt_factor"]
        adaptive = cfg["adaptive"]
        refresh_every = cfg.get("refresh_every")
        refresh_mode = cfg.get("refresh_mode")
        label = (
            f"{solver}_iter{max_iter}_cfl{str(cfl_scale).replace('.', '')}"
            f"_dt{str(dt_factor).replace('.', '')}_{'adapt' if adaptive else 'fixed'}"
        )
        if refresh_every and refresh_every > 1 and refresh_mode:
            label += f"_refresh{refresh_every}{refresh_mode}"
        env = {
            "ISLAM_FAST_NODE_SOLVER": solver,
            "ISLAM_NODE_MAX_ITER": str(max_iter),
            "ISLAM_FAST_CFL_SCALE": str(cfl_scale),
            "ISLAM_FAST_DT_INCREASE_FACTOR": str(dt_factor),
            "ISLAM_FAST_ADAPTIVE": "1" if adaptive else "0",
            "ISLAM_USE_NODE_RESPONSE_TABLE": "1",
            "ISLAM_SAVE_INTERNAL_NODE_HISTORY": "0",
            "ISLAM_FAST_SAVE_NODE_HISTORY": "0",
            "ISLAM_SAVE_RUN_SUMMARY": "1",
        }
        if adaptive:
            env.update(
                {
                    "ISLAM_FAST_ADAPTIVE_MIN_STREAK": "2",
                    "ISLAM_FAST_ADAPTIVE_LEVEL_DELTA": "0.03",
                    "ISLAM_FAST_ADAPTIVE_RESIDUAL_FACTOR": "2.0",
                }
            )
        if refresh_every and refresh_every > 1 and refresh_mode:
            env.update(
                {
                    "ISLAM_FAST_NODE_REFRESH_EVERY": str(refresh_every),
                    "ISLAM_FAST_NODE_REFRESH_MODE": str(refresh_mode),
                    "ISLAM_FAST_NODE_REFRESH_WARMUP_STEPS": "2",
                }
            )
        note = f"{solver}, iter={max_iter}, cfl={cfl_scale}, dt_factor={dt_factor}, adaptive={adaptive}"
        if refresh_every and refresh_every > 1 and refresh_mode:
            note += f", refresh_every={refresh_every}, refresh_mode={refresh_mode}"
        candidates.append(
            {
                "label": label,
                "kind": "run",
                "output_path": candidate_result_dir(label),
                "env": env,
                "notes": note,
            }
        )
    return candidates


def run_candidate(cfg, force=False):
    output_dir = Path(cfg["output_path"])
    if output_dir.exists() and not force:
        prior = load_existing_candidate_report(cfg["label"])
        summary = load_run_summary(output_dir)
        return {
            "candidate_dir": output_dir,
            "wall_time_s": None if prior is None else prior.get("wall_time_s"),
            "model_time_s": (
                None if summary is None else float(summary.get("calculation_time", math.nan))
            ) if prior is None else prior.get("model_time_s"),
            "step_count": (
                None if summary is None else int(summary.get("step_count", 0))
            ) if prior is None else prior.get("step_count"),
        }
    env = os.environ.copy()
    env.update(BASE_ENV)
    env.update(cfg["env"])
    env["ISLAM_OUTPUT_PATH"] = str(output_dir.relative_to(PROJECT_ROOT))
    env["ISLAM_SIM_END_TIME"] = SIM_END_TIME
    stdout_log = SWEEP_RUN_ROOT / f"{cfg['label']}.stdout.log"
    stderr_log = SWEEP_RUN_ROOT / f"{cfg['label']}.stderr.log"
    SWEEP_RUN_ROOT.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    proc = subprocess.run(
        ["conda", "run", "-n", "python311", "python", "Islam.py"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    wall_time_s = time.perf_counter() - t0
    stdout_log.write_text(proc.stdout, encoding="utf-8")
    stderr_log.write_text(proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"{cfg['label']} failed: {proc.stderr}")
    summary = load_run_summary(output_dir)
    return {
        "candidate_dir": output_dir,
        "wall_time_s": round(wall_time_s, 6),
        "model_time_s": None if summary is None else float(summary.get("calculation_time", math.nan)),
        "step_count": None if summary is None else int(summary.get("step_count", 0)),
    }


def write_matrix(rows):
    matrix_path = REPORT_ROOT / "fast_sweep_matrix.md"
    lines = [
        "# FAST Sweep Matrix",
        "",
        "40-hour FAST candidate summary against the accepted exact baseline.",
        "",
        as_markdown_table(rows),
        "",
    ]
    matrix_path.write_text("\n".join(lines), encoding="utf-8")
    return matrix_path


def write_top_candidates(rows):
    rows_sorted = sorted(
        rows,
        key=lambda r: (
            float("inf") if r["wall_time_s"] is None else r["wall_time_s"],
            float("inf") if r["max_abs_overall"] is None else r["max_abs_overall"],
        ),
    )
    front = pareto_front(rows_sorted)
    top_path = REPORT_ROOT / "fast_sweep_top_candidates.md"
    lines = [
        "# FAST Sweep Top Candidates",
        "",
        "## Pareto Front",
        "",
        as_markdown_table(front),
        "",
        "## Fastest Five",
        "",
        as_markdown_table(rows_sorted[:5]),
        "",
    ]
    top_path.write_text("\n".join(lines), encoding="utf-8")
    return top_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-generated", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--label-contains", default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    all_rows = []

    for cfg in build_existing_candidates():
        payload = result_metrics_payload(
            cfg["label"],
            cfg["candidate_dir"],
            wall_time_s=cfg["wall_time_s"],
            model_time_s=cfg["model_time_s"],
            step_count=cfg["step_count"],
        )
        write_candidate_report(payload)
        all_rows.append(record_row(payload, "existing", cfg["notes"]))

    all_generated_configs = build_sweep_candidates()
    generated_by_label = {cfg["label"]: cfg for cfg in all_generated_configs}
    generated = list(all_generated_configs)
    if args.label_contains:
        needle = str(args.label_contains)
        generated = [cfg for cfg in generated if needle in cfg["label"]]
    if args.limit is not None:
        generated = generated[: args.limit]

    if args.run_generated:
        for cfg in generated:
            run_info = run_candidate(cfg, force=args.force)
            payload = result_metrics_payload(
                cfg["label"],
                run_info["candidate_dir"],
                wall_time_s=run_info["wall_time_s"],
                model_time_s=run_info["model_time_s"],
                step_count=run_info["step_count"],
            )
            write_candidate_report(payload)
            all_rows.append(record_row(payload, "generated", cfg["notes"]))

    for label, cfg in sorted(generated_by_label.items()):
        if any(row["label"] == label for row in all_rows):
            continue
        payload = load_existing_candidate_report(label)
        if payload is None:
            continue
        all_rows.append(record_row(payload, "generated", cfg["notes"]))

    rows_sorted = sorted(
        all_rows,
        key=lambda r: (
            float("inf") if r["wall_time_s"] is None else r["wall_time_s"],
            float("inf") if r["max_abs_overall"] is None else r["max_abs_overall"],
        ),
    )
    matrix_path = write_matrix(rows_sorted)
    top_path = write_top_candidates(rows_sorted)
    print(matrix_path)
    print(top_path)


if __name__ == "__main__":
    main()
