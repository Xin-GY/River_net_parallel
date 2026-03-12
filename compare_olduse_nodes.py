from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr


matplotlib.use("Agg", force=True)


RIVER_EXPORT_GRIDS = {
    "river8": [0, 14],
    "river9": [0, 14],
    "river10": [0, 19],
    "river11": [0, 11],
    "river12": [0, 35],
    "river13": [0, 19],
}

PLOT_SPECS = {
    "node11_level": {
        "obs": "old_use/Islam_real_data/node11_level.csv",
        "var": "level",
        "curves": [
            ("river8", 14, "river8[14]"),
            ("river9", 14, "river9[14]"),
            ("river11", 11, "river11[11]"),
            ("river12", 0, "river12[0]"),
        ],
    },
    "node11_Q": {
        "obs": "old_use/Islam_real_data/node11_Q.csv",
        "var": "Q",
        "use_abs": True,
        "curves": [
            ("river8", 14, "river8[14]"),
            ("river9", 14, "river9[14]"),
            ("river11", 11, "river11[11]"),
            ("river12", 0, "river12[0]"),
        ],
        "mean_label": "node11 mean(|Q|)",
    },
    "node12_level": {
        "obs": "old_use/Islam_real_data/node12_level.csv",
        "var": "level",
        "curves": [
            ("river10", 19, "river10[19]"),
            ("river11", 0, "river11[0]"),
            ("river13", 0, "river13[0]"),
        ],
    },
    "node12_Q": {
        "obs": "old_use/Islam_real_data/node12_Q.csv",
        "var": "Q",
        "use_abs": True,
        "curves": [
            ("river10", 19, "river10[19]"),
            ("river11", 0, "river11[0]"),
            ("river13", 0, "river13[0]"),
        ],
        "mean_label": "node12 mean(|Q|)",
    },
}


def load_observed(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df.columns = [col.replace("\ufeff", "").strip().lower() for col in df.columns]
    df["x"] = pd.to_numeric(df["x"], errors="coerce")
    df["y"] = pd.to_numeric(df["y"], errors="coerce")
    return df.dropna(subset=["x", "y"]).sort_values("x").reset_index(drop=True)


def extract_subset(result_dir: Path, river_name: str, grids: list[int], out_dir: Path) -> pd.DataFrame:
    nc_path = result_dir / f"{river_name}_interpolated_output.nc"
    ds = xr.open_dataset(nc_path)
    try:
        frames = []
        times = np.asarray(ds["time"].values, dtype=float)
        for grid in grids:
            for var in ("level", "Q"):
                values = np.asarray(ds[var].isel(space=grid).values, dtype=float)
                frames.append(
                    pd.DataFrame(
                        {
                            "time": times,
                            "grid": grid,
                            "var": var,
                            "value": values,
                        }
                    )
                )
    finally:
        ds.close()

    subset = pd.concat(frames, ignore_index=True).sort_values(["var", "grid", "time"]).reset_index(drop=True)
    subset.to_csv(out_dir / f"{river_name}_subset.csv", index=False)
    return subset


def interpolate_metric(model_time_hours: np.ndarray, model_values: np.ndarray, obs_hours: np.ndarray, obs_values: np.ndarray) -> dict[str, float]:
    interp = np.interp(obs_hours, model_time_hours, model_values)
    residual = interp - obs_values
    denom = np.sum((obs_values - obs_values.mean()) ** 2)
    nse = np.nan if denom <= 0.0 else 1.0 - np.sum(residual ** 2) / denom
    return {
        "sample_count": float(len(obs_values)),
        "mae": float(np.mean(np.abs(residual))),
        "rmse": float(np.sqrt(np.mean(residual ** 2))),
        "bias": float(np.mean(residual)),
        "max_abs_error": float(np.max(np.abs(residual))),
        "nse": float(nse) if np.isfinite(nse) else np.nan,
    }


def plot_spec(name: str, spec: dict, subset_data: dict[str, pd.DataFrame], out_dir: Path) -> None:
    observed = load_observed(Path(spec["obs"]))
    obs_hours = observed["x"].to_numpy(dtype=float)
    obs_values = observed["y"].to_numpy(dtype=float)

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(obs_hours, obs_values, label="observed", color="#1f77b4", linestyle="--", linewidth=2.0)

    metric_rows = []
    q_curves = []

    for river_name, grid, label in spec["curves"]:
        df = subset_data[river_name]
        var_mask = df["var"] == spec["var"]
        grid_mask = df["grid"] == grid
        series = df[var_mask & grid_mask].copy()
        values = series["value"].to_numpy(dtype=float)
        if spec.get("use_abs", False):
            values = np.abs(values)
        hours = series["time"].to_numpy(dtype=float) / 3600.0
        q_curves.append((hours, values, label))
        ax.plot(hours, values, label=label, linewidth=1.4)
        metrics = interpolate_metric(hours, values, obs_hours, obs_values)
        metrics["series"] = label
        metric_rows.append(metrics)

    if spec.get("mean_label"):
        base_hours = q_curves[0][0]
        stacked = np.vstack([np.interp(base_hours, hours, values) for hours, values, _ in q_curves])
        mean_values = stacked.mean(axis=0)
        ax.plot(base_hours, mean_values, label=spec["mean_label"], linewidth=2.0, color="#d62728")
        metrics = interpolate_metric(base_hours, mean_values, obs_hours, obs_values)
        metrics["series"] = spec["mean_label"]
        metric_rows.append(metrics)

    ax.set_title(name.replace("_", " "))
    ax.set_xlabel("Time (hours)")
    ax.set_ylabel("Level (m)" if spec["var"] == "level" else "Discharge magnitude")
    ax.grid(True, alpha=0.3)
    ax.legend()

    fig.tight_layout()
    fig.savefig(out_dir / f"{name}_compare.png", dpi=180)
    plt.close(fig)

    metrics_df = pd.DataFrame(metric_rows)
    cols = ["series", "sample_count", "mae", "rmse", "bias", "max_abs_error", "nse"]
    metrics_df[cols].to_csv(out_dir / f"{name}_metrics.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce old_use node comparison plots from new serial Islam outputs.")
    parser.add_argument("--result-dir", default="result/Islam_olduse_serial")
    args = parser.parse_args()

    result_dir = Path(args.result_dir)
    out_dir = result_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    subset_data = {
        river_name: extract_subset(result_dir, river_name, grids, out_dir)
        for river_name, grids in RIVER_EXPORT_GRIDS.items()
    }

    for name, spec in PLOT_SPECS.items():
        plot_spec(name, spec, subset_data, out_dir)


if __name__ == "__main__":
    main()
