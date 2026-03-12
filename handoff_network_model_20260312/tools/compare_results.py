#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


CONTROL_POINT_SPECS = [
    ("node11_level", "level", 0),
    ("node11_Q", "Q", 0),
    ("node12_level", "level", 11),
    ("node12_Q", "Q", 11),
]


def _numeric_metrics(a, b, rtol, atol):
    arr_a = np.asarray(a)
    arr_b = np.asarray(b)
    if arr_a.shape != arr_b.shape:
        return {
            "shape_match": False,
            "shape_a": list(arr_a.shape),
            "shape_b": list(arr_b.shape),
        }

    arr_a = arr_a.astype(float, copy=False)
    arr_b = arr_b.astype(float, copy=False)
    both_nan = np.isnan(arr_a) & np.isnan(arr_b)
    finite_mask = np.isfinite(arr_a) & np.isfinite(arr_b)
    valid = both_nan | finite_mask

    if not np.all(valid):
        return {
            "shape_match": True,
            "valid_mask_match": False,
            "invalid_count": int((~valid).sum()),
            "allclose": False,
        }

    if np.any(finite_mask):
        diff = np.abs(arr_a[finite_mask] - arr_b[finite_mask])
        max_abs = float(diff.max())
        mean_abs = float(diff.mean())
        rmse = float(np.sqrt(np.mean(diff * diff)))
    else:
        max_abs = 0.0
        mean_abs = 0.0
        rmse = 0.0

    return {
        "shape_match": True,
        "valid_mask_match": True,
        "max_abs": max_abs,
        "mean_abs": mean_abs,
        "rmse": rmse,
        "allclose": bool(np.allclose(arr_a, arr_b, rtol=rtol, atol=atol, equal_nan=True)),
    }


def compare_csv(baseline_path, candidate_path, rtol, atol):
    base_df = pd.read_csv(baseline_path)
    cand_df = pd.read_csv(candidate_path)
    result = {
        "file": str(candidate_path.name),
        "type": "csv",
        "rows_baseline": int(len(base_df)),
        "rows_candidate": int(len(cand_df)),
        "columns_baseline": list(base_df.columns),
        "columns_candidate": list(cand_df.columns),
        "column_metrics": {},
    }
    common_cols = [c for c in base_df.columns if c in cand_df.columns]
    for col in common_cols:
        if pd.api.types.is_numeric_dtype(base_df[col]) and pd.api.types.is_numeric_dtype(cand_df[col]):
            result["column_metrics"][col] = _numeric_metrics(
                base_df[col].to_numpy(),
                cand_df[col].to_numpy(),
                rtol=rtol,
                atol=atol,
            )
    result["allclose"] = all(
        metric.get("allclose", False) for metric in result["column_metrics"].values()
    )
    return result


def compare_dataset(baseline_path, candidate_path, rtol, atol):
    base_ds = xr.open_dataset(baseline_path, engine="h5netcdf")
    cand_ds = xr.open_dataset(candidate_path, engine="h5netcdf")
    result = {
        "file": str(candidate_path.name),
        "type": "netcdf",
        "dims_baseline": {k: int(v) for k, v in base_ds.sizes.items()},
        "dims_candidate": {k: int(v) for k, v in cand_ds.sizes.items()},
        "coord_metrics": {},
        "data_var_metrics": {},
    }

    common_coords = [c for c in base_ds.coords if c in cand_ds.coords]
    for name in common_coords:
        if np.issubdtype(base_ds[name].dtype, np.number) and np.issubdtype(cand_ds[name].dtype, np.number):
            result["coord_metrics"][name] = _numeric_metrics(
                base_ds[name].to_numpy(),
                cand_ds[name].to_numpy(),
                rtol=rtol,
                atol=atol,
            )

    common_data_vars = [v for v in base_ds.data_vars if v in cand_ds.data_vars]
    for name in common_data_vars:
        if np.issubdtype(base_ds[name].dtype, np.number) and np.issubdtype(cand_ds[name].dtype, np.number):
            result["data_var_metrics"][name] = _numeric_metrics(
                base_ds[name].to_numpy(),
                cand_ds[name].to_numpy(),
                rtol=rtol,
                atol=atol,
            )

    result["allclose"] = all(
        metric.get("allclose", False)
        for metric in list(result["coord_metrics"].values()) + list(result["data_var_metrics"].values())
    )
    return result


def compare_control_points(baseline_dir, candidate_dir, rtol, atol):
    base_path = baseline_dir / "river11_interpolated_output.nc"
    cand_path = candidate_dir / "river11_interpolated_output.nc"
    if not base_path.exists() or not cand_path.exists():
        return {}

    base_ds = xr.open_dataset(base_path, engine="h5netcdf")
    cand_ds = xr.open_dataset(cand_path, engine="h5netcdf")
    result = {}
    for name, var, idx in CONTROL_POINT_SPECS:
        result[name] = _numeric_metrics(
            base_ds[var].isel(space=idx).to_numpy(),
            cand_ds[var].isel(space=idx).to_numpy(),
            rtol=rtol,
            atol=atol,
        )
    return result


def compare_final_state(baseline_dir, candidate_dir, rtol, atol):
    base_path = baseline_dir / "river11_interpolated_output.nc"
    cand_path = candidate_dir / "river11_interpolated_output.nc"
    if not base_path.exists() or not cand_path.exists():
        return {}

    base_ds = xr.open_dataset(base_path, engine="h5netcdf")
    cand_ds = xr.open_dataset(cand_path, engine="h5netcdf")
    result = {}
    for var in ["depth", "level", "U", "Q"]:
        if var in base_ds and var in cand_ds:
            result[var] = _numeric_metrics(
                base_ds[var].isel(time=-1).to_numpy(),
                cand_ds[var].isel(time=-1).to_numpy(),
                rtol=rtol,
                atol=atol,
            )
    return result


def compare_result_dirs(baseline_dir, candidate_dir, rtol, atol):
    baseline_dir = Path(baseline_dir)
    candidate_dir = Path(candidate_dir)

    report = {
        "baseline_dir": str(baseline_dir.resolve()),
        "candidate_dir": str(candidate_dir.resolve()),
        "rtol": float(rtol),
        "atol": float(atol),
        "files": [],
        "control_points": compare_control_points(baseline_dir, candidate_dir, rtol, atol),
        "final_state": compare_final_state(baseline_dir, candidate_dir, rtol, atol),
    }

    for pattern in ["*.csv", "*.nc"]:
        for cand_path in sorted(candidate_dir.glob(pattern)):
            base_path = baseline_dir / cand_path.name
            if not base_path.exists():
                continue
            if cand_path.suffix == ".csv":
                report["files"].append(compare_csv(base_path, cand_path, rtol, atol))
            elif cand_path.suffix == ".nc":
                report["files"].append(compare_dataset(base_path, cand_path, rtol, atol))

    all_flags = []
    for item in report["files"]:
        all_flags.append(bool(item.get("allclose", False)))
    for metrics in report["control_points"].values():
        all_flags.append(bool(metrics.get("allclose", False)))
    for metrics in report["final_state"].values():
        all_flags.append(bool(metrics.get("allclose", False)))
    report["allclose"] = all(all_flags) if all_flags else False
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline_dir")
    parser.add_argument("candidate_dir")
    parser.add_argument("--rtol", type=float, default=1e-12)
    parser.add_argument("--atol", type=float, default=1e-12)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    report = compare_result_dirs(args.baseline_dir, args.candidate_dir, args.rtol, args.atol)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
