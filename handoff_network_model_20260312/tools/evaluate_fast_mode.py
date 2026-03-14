#!/usr/bin/env python3
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from result.river11_compare_utils import load_river11_series  # noqa: E402


CONTROL_POINT_SPECS = [
    ("node11_level", "level", 0),
    ("node11_Q", "Q", 0),
    ("node12_level", "level", 11),
    ("node12_Q", "Q", 11),
]


def numeric_metrics(a, b):
    arr_a = np.asarray(a, dtype=float)
    arr_b = np.asarray(b, dtype=float)
    if arr_a.shape != arr_b.shape:
        return {
            "shape_match": False,
            "shape_a": list(arr_a.shape),
            "shape_b": list(arr_b.shape),
        }
    diff = np.abs(arr_a - arr_b)
    return {
        "shape_match": True,
        "max_abs": float(np.nanmax(diff)) if diff.size else 0.0,
        "mean_abs": float(np.nanmean(diff)) if diff.size else 0.0,
        "rmse": float(np.sqrt(np.nanmean(diff * diff))) if diff.size else 0.0,
    }


def parse_time_file(path):
    if path is None:
        return None
    path = Path(path)
    if not path.exists():
        return None
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) == 2 and parts[0] in {"real", "user", "sys"}:
            try:
                result[parts[0]] = float(parts[1])
            except ValueError:
                pass
    return result or None


def load_run_summary(result_dir):
    path = Path(result_dir) / "run_summary.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def detect_flow_sign(ds):
    q_blocks = [
        np.asarray(ds["Q"].isel(space=0).to_numpy(), dtype=float),
        np.asarray(ds["Q"].isel(space=11).to_numpy(), dtype=float),
    ]
    q_all = np.concatenate(q_blocks)
    return 1 if float(np.nanmean(q_all)) >= 0.0 else -1


def peak_summary(name, time_h, values):
    arr_t = np.asarray(time_h, dtype=float)
    arr_v = np.asarray(values, dtype=float)
    if "Q" in name:
        idx = int(np.nanargmax(np.abs(arr_v)))
    else:
        idx = int(np.nanargmax(arr_v))
    return {
        "peak_value": float(arr_v[idx]),
        "peak_abs": float(abs(arr_v[idx])),
        "peak_time_h": float(arr_t[idx]),
    }


def compare_control_points(baseline_dir, candidate_dir):
    base_ds = xr.open_dataset(Path(baseline_dir) / "river11_interpolated_output.nc", engine="h5netcdf")
    cand_ds = xr.open_dataset(Path(candidate_dir) / "river11_interpolated_output.nc", engine="h5netcdf")
    base_time_h = np.asarray(base_ds["time"].to_numpy(), dtype=float) / 3600.0
    cand_time_h = np.asarray(cand_ds["time"].to_numpy(), dtype=float) / 3600.0
    base_q_sign = detect_flow_sign(base_ds)
    cand_q_sign = detect_flow_sign(cand_ds)

    report = {}
    for name, var, idx in CONTROL_POINT_SPECS:
        base_values = np.asarray(base_ds[var].isel(space=idx).to_numpy(), dtype=float)
        cand_values = np.asarray(cand_ds[var].isel(space=idx).to_numpy(), dtype=float)
        if var == "Q":
            base_values = base_q_sign * base_values
            cand_values = cand_q_sign * cand_values
        cand_on_base = np.interp(base_time_h, cand_time_h, cand_values)
        metrics = numeric_metrics(base_values, cand_on_base)
        base_peak = peak_summary(name, base_time_h, base_values)
        cand_peak = peak_summary(name, base_time_h, cand_on_base)
        report[name] = {
            **metrics,
            "baseline_peak_value": base_peak["peak_value"],
            "candidate_peak_value": cand_peak["peak_value"],
            "peak_value_error": float(cand_peak["peak_value"] - base_peak["peak_value"]),
            "peak_abs_error": float(cand_peak["peak_abs"] - base_peak["peak_abs"]),
            "baseline_peak_time_h": base_peak["peak_time_h"],
            "candidate_peak_time_h": cand_peak["peak_time_h"],
            "peak_arrival_time_error_h": float(cand_peak["peak_time_h"] - base_peak["peak_time_h"]),
        }
    return report


def compare_nse(real_dir, baseline_dir, candidate_dir):
    baseline_rows, base_meta = load_river11_series(Path(baseline_dir), Path(real_dir), flow_direction="auto")
    candidate_rows, cand_meta = load_river11_series(Path(candidate_dir), Path(real_dir), flow_direction="auto")
    base_metrics = {row["name"]: row["metrics"] for row in baseline_rows}
    cand_metrics = {row["name"]: row["metrics"] for row in candidate_rows}
    mean_base = float(np.nanmean([rec["nse"] for rec in base_metrics.values()]))
    mean_cand = float(np.nanmean([rec["nse"] for rec in cand_metrics.values()]))
    return {
        "baseline_mean_nse": mean_base,
        "candidate_mean_nse": mean_cand,
        "mean_nse_delta": float(mean_cand - mean_base),
        "baseline_flow_sign": base_meta,
        "candidate_flow_sign": cand_meta,
        "series": {
            name: {
                "baseline_nse": float(base_metrics[name]["nse"]),
                "candidate_nse": float(cand_metrics[name]["nse"]),
                "nse_delta": float(cand_metrics[name]["nse"] - base_metrics[name]["nse"]),
                "baseline_rmse": float(base_metrics[name]["rmse"]),
                "candidate_rmse": float(cand_metrics[name]["rmse"]),
            }
            for name in sorted(base_metrics)
        },
    }


def compare_internal_node_history(baseline_dir, candidate_dir):
    base_path = Path(baseline_dir) / "internal_node_history.csv"
    cand_path = Path(candidate_dir) / "internal_node_history.csv"
    if not base_path.exists() or not cand_path.exists():
        return {
            "available": False,
            "reason": "missing_file",
        }
    base_df = pd.read_csv(base_path)
    cand_df = pd.read_csv(cand_path)
    common_cols = [
        col for col in base_df.columns
        if col in cand_df.columns and pd.api.types.is_numeric_dtype(base_df[col]) and pd.api.types.is_numeric_dtype(cand_df[col])
    ]
    common_cols = [col for col in common_cols if col.endswith("_level") or col.endswith("_Qnet")]
    if not common_cols:
        return {
            "available": False,
            "reason": "no_common_numeric_columns",
        }
    column_metrics = {
        col: numeric_metrics(base_df[col].to_numpy(), cand_df[col].to_numpy())
        for col in common_cols
    }
    return {
        "available": True,
        "rows_baseline": int(len(base_df)),
        "rows_candidate": int(len(cand_df)),
        "max_abs": float(max(rec["max_abs"] for rec in column_metrics.values())),
        "mean_abs": float(np.mean([rec["mean_abs"] for rec in column_metrics.values()])),
        "columns": column_metrics,
    }


def compare_volume(baseline_dir, candidate_dir):
    base = load_run_summary(baseline_dir)
    cand = load_run_summary(candidate_dir)
    if base is None or cand is None:
        return {
            "available": False,
            "reason": "missing_run_summary",
        }
    base_rivers = {rec["river"]: rec for rec in base.get("rivers", [])}
    cand_rivers = {rec["river"]: rec for rec in cand.get("rivers", [])}
    common = sorted(set(base_rivers) & set(cand_rivers))
    river_metrics = {}
    max_delta = 0.0
    for name in common:
        delta = float(cand_rivers[name]["relative_volume_change"] - base_rivers[name]["relative_volume_change"])
        max_delta = max(max_delta, abs(delta))
        river_metrics[name] = {
            "baseline_relative_volume_change": float(base_rivers[name]["relative_volume_change"]),
            "candidate_relative_volume_change": float(cand_rivers[name]["relative_volume_change"]),
            "relative_volume_change_delta": delta,
        }
    return {
        "available": True,
        "baseline_network_relative_volume_change": float(base["network_relative_volume_change"]),
        "candidate_network_relative_volume_change": float(cand["network_relative_volume_change"]),
        "network_relative_volume_change_delta": float(
            cand["network_relative_volume_change"] - base["network_relative_volume_change"]
        ),
        "max_abs_river_relative_volume_change_delta": float(max_delta),
        "rivers": river_metrics,
    }


def build_markdown(report):
    lines = [
        "# FAST_MODE Evaluation",
        "",
        f"- baseline: {report['baseline_dir']}",
        f"- candidate: {report['candidate_dir']}",
        "",
        "## Speed",
    ]
    speed = report["speed"]
    if speed["baseline_wall"] or speed["candidate_wall"]:
        lines.append(f"- baseline wall: {speed['baseline_wall']}")
        lines.append(f"- candidate wall: {speed['candidate_wall']}")
    lines.append(f"- baseline model time: {speed['baseline_model_time_s']}")
    lines.append(f"- candidate model time: {speed['candidate_model_time_s']}")
    lines.append(f"- wall speedup: {speed['wall_speedup']}")
    lines.append(f"- model speedup: {speed['model_speedup']}")
    lines.extend(["", "## NSE"])
    lines.append(f"- baseline mean NSE: {report['nse']['baseline_mean_nse']:.6f}")
    lines.append(f"- candidate mean NSE: {report['nse']['candidate_mean_nse']:.6f}")
    lines.append(f"- mean NSE delta: {report['nse']['mean_nse_delta']:.6f}")
    lines.extend(["", "## Control Point Error"])
    for name, rec in report["control_points"].items():
        lines.append(
            f"- {name}: max_abs={rec['max_abs']:.6g}, rmse={rec['rmse']:.6g}, "
            f"peak_err={rec['peak_value_error']:.6g}, peak_dt_h={rec['peak_arrival_time_error_h']:.6g}"
        )
    lines.extend(["", "## Volume"])
    vol = report["volume"]
    if vol["available"]:
        lines.append(f"- baseline network relative volume change: {vol['baseline_network_relative_volume_change']:.6g}")
        lines.append(f"- candidate network relative volume change: {vol['candidate_network_relative_volume_change']:.6g}")
        lines.append(f"- network relative volume delta: {vol['network_relative_volume_change_delta']:.6g}")
        lines.append(f"- max river relative volume delta: {vol['max_abs_river_relative_volume_change_delta']:.6g}")
    else:
        lines.append(f"- unavailable: {vol['reason']}")
    lines.extend(["", "## Internal Node History"])
    hist = report["internal_node_history"]
    if hist["available"]:
        lines.append(f"- max_abs={hist['max_abs']:.6g}, mean_abs={hist['mean_abs']:.6g}")
    else:
        lines.append(f"- unavailable: {hist['reason']}")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline_dir")
    parser.add_argument("candidate_dir")
    parser.add_argument("--real-dir", default=str(ROOT / "result" / "Islam_real_data"))
    parser.add_argument("--baseline-time-file", default=None)
    parser.add_argument("--candidate-time-file", default=None)
    parser.add_argument("--out-json", default=None)
    parser.add_argument("--out-md", default=None)
    args = parser.parse_args()

    baseline_dir = Path(args.baseline_dir)
    candidate_dir = Path(args.candidate_dir)
    baseline_summary = load_run_summary(baseline_dir)
    candidate_summary = load_run_summary(candidate_dir)
    baseline_wall = parse_time_file(args.baseline_time_file)
    candidate_wall = parse_time_file(args.candidate_time_file)
    baseline_model_time = None if baseline_summary is None else float(baseline_summary.get("calculation_time", math.nan))
    candidate_model_time = None if candidate_summary is None else float(candidate_summary.get("calculation_time", math.nan))

    report = {
        "baseline_dir": str(baseline_dir.resolve()),
        "candidate_dir": str(candidate_dir.resolve()),
        "speed": {
            "baseline_wall": baseline_wall,
            "candidate_wall": candidate_wall,
            "baseline_model_time_s": baseline_model_time,
            "candidate_model_time_s": candidate_model_time,
            "wall_speedup": (
                None if not baseline_wall or not candidate_wall else float(baseline_wall["real"] / candidate_wall["real"])
            ),
            "model_speedup": (
                None if baseline_model_time in (None, 0.0) or candidate_model_time in (None, 0.0)
                else float(baseline_model_time / candidate_model_time)
            ),
        },
        "nse": compare_nse(args.real_dir, baseline_dir, candidate_dir),
        "control_points": compare_control_points(baseline_dir, candidate_dir),
        "volume": compare_volume(baseline_dir, candidate_dir),
        "internal_node_history": compare_internal_node_history(baseline_dir, candidate_dir),
    }

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out_json:
        Path(args.out_json).write_text(text, encoding="utf-8")
    md = build_markdown(report)
    if args.out_md:
        Path(args.out_md).write_text(md, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
