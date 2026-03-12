from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr


matplotlib.use("Agg", force=True)


def load_observed_series(csv_path: Path, sim_start: str) -> pd.Series:
    df = pd.read_csv(csv_path)
    df.columns = [col.strip() for col in df.columns]
    hours = pd.to_numeric(df.iloc[:, 0], errors="coerce")
    values = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    mask = hours.notna() & values.notna()
    times = pd.to_datetime(sim_start) + pd.to_timedelta(hours[mask].to_numpy(), unit="h")
    series = pd.Series(values[mask].to_numpy(), index=times, name="observed_level")
    return series.sort_index()


def load_model_series(nc_path: Path, sim_start: str, space_index: int) -> pd.Series:
    ds = xr.open_dataset(nc_path)
    try:
        total_space = int(ds.sizes["space"])
        index = space_index if space_index >= 0 else total_space + space_index
        if index < 0 or index >= total_space:
            raise IndexError(f"space_index={space_index} out of bounds for space={total_space}")
        seconds = pd.to_numeric(pd.Index(ds["time"].values), errors="coerce")
        values = ds["level"].isel(space=index).to_numpy()
    finally:
        ds.close()
    times = pd.to_datetime(sim_start) + pd.to_timedelta(seconds, unit="s")
    return pd.Series(values, index=times, name="model_level").sort_index()


def build_comparison_dataframe(model: pd.Series, observed: pd.Series) -> pd.DataFrame:
    observed_seconds = (observed.index - observed.index[0]).total_seconds().to_numpy(dtype=float)
    model_seconds = (model.index - observed.index[0]).total_seconds().to_numpy(dtype=float)
    interpolated_model = np.interp(
        observed_seconds,
        model_seconds,
        model.to_numpy(dtype=float),
        left=np.nan,
        right=np.nan,
    )
    comparison = pd.DataFrame(
        {
            "time": observed.index,
            "observed_level": observed.to_numpy(dtype=float),
            "model_level": interpolated_model,
        }
    )
    comparison["residual"] = comparison["model_level"] - comparison["observed_level"]
    comparison = comparison.dropna().reset_index(drop=True)
    return comparison


def compute_metrics(comparison: pd.DataFrame) -> pd.DataFrame:
    residual = comparison["residual"].to_numpy(dtype=float)
    observed = comparison["observed_level"].to_numpy(dtype=float)
    denominator = np.sum((observed - observed.mean()) ** 2)
    nse = np.nan if denominator <= 0.0 else 1.0 - np.sum(residual ** 2) / denominator
    metrics = pd.DataFrame(
        [
            ("sample_count", float(len(comparison))),
            ("mae", float(np.mean(np.abs(residual)))),
            ("rmse", float(np.sqrt(np.mean(residual ** 2)))),
            ("bias", float(np.mean(residual))),
            ("max_abs_error", float(np.max(np.abs(residual)))),
            ("nse", float(nse) if np.isfinite(nse) else np.nan),
        ],
        columns=["metric", "value"],
    )
    return metrics


def make_plot(comparison: pd.DataFrame, metrics: pd.DataFrame, output_path: Path, title: str) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True, constrained_layout=True)

    axes[0].plot(comparison["time"], comparison["observed_level"], label="Observed", color="#1f77b4", linewidth=1.8)
    axes[0].plot(comparison["time"], comparison["model_level"], label="Model", color="#d62728", linewidth=1.5)
    axes[0].set_ylabel("Water level (m)")
    axes[0].set_title(title)
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()

    axes[1].plot(comparison["time"], comparison["residual"], color="#444444", linewidth=1.2)
    axes[1].axhline(0.0, color="#000000", linewidth=0.8, linestyle="--")
    axes[1].set_ylabel("Model - Obs (m)")
    axes[1].set_xlabel("Time")
    axes[1].grid(True, alpha=0.3)

    metric_text = "\n".join(f"{row.metric}: {row.value:.4f}" for row in metrics.itertuples(index=False))
    axes[1].text(
        0.01,
        0.98,
        metric_text,
        transform=axes[1].transAxes,
        va="top",
        ha="left",
        fontsize=9,
        bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "#cccccc"},
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Islam model downstream stage against observed data.")
    parser.add_argument("--nc-path", default="result/Islam_base/river14_interpolated_output.nc")
    parser.add_argument("--obs-path", default="bound/Islam_level_out.csv")
    parser.add_argument("--output-dir", default="result/Islam_base/comparison")
    parser.add_argument("--sim-start", default="2024-01-01 00:00:00")
    parser.add_argument("--space-index", type=int, default=-1, help="Model space index to compare, default is last cell.")
    args = parser.parse_args()

    nc_path = Path(args.nc_path)
    obs_path = Path(args.obs_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    observed = load_observed_series(obs_path, args.sim_start)
    model = load_model_series(nc_path, args.sim_start, args.space_index)
    comparison = build_comparison_dataframe(model, observed)
    if comparison.empty:
        raise RuntimeError("Comparison dataframe is empty after time alignment.")

    metrics = compute_metrics(comparison)
    comparison.to_csv(output_dir / "river14_level_comparison.csv", index=False)
    metrics.to_csv(output_dir / "river14_level_metrics.csv", index=False)
    make_plot(
        comparison,
        metrics,
        output_dir / "river14_level_vs_observed.png",
        title="Islam downstream stage: model last cell vs observed boundary level",
    )


if __name__ == "__main__":
    main()
