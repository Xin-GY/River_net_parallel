import os

# ===== OpenMP / BLAS 线程控制（必须放在数值库导入之前） =====
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OMP_MAX_ACTIVE_LEVELS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("KMP_WARNINGS", "0")

import argparse
import json
import platform
import sys
import time
from pathlib import Path
from typing import Dict, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import Islam_gpt_hardcoded as islam

# =========================
# 可直接修改的基准配置
# =========================
SERIAL_BASELINE = True                 # 是否加入“非多进程”基准（workers=0）
WORKER_START = 1                       # 多进程测试起始进程数
WORKER_END = 10                        # 多进程测试结束进程数
REPEATS = 1                            # 每个配置重复次数
YIELD_STEP = 3600.0                    # 模型回报间隔
PRINT_PROGRESS_DURING_BENCHMARK = False
EXPORT_GRAPH_ON_FIRST_RUN = False
OUTPUT_DIR = Path("result/Islam_benchmark")
TEMP_RUN_ROOT = OUTPUT_DIR / "runs"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def configure_runtime(parallel_workers: int,
                      output_path: Path,
                      parallel_mode: str = "process") -> None:
    """同步修改 Islam 入口脚本中的全局并行配置。"""
    islam.PARALLEL_MODE = str(parallel_mode)
    islam.PARALLEL_WORKERS = int(parallel_workers)
    islam.output_path = str(output_path)
    islam.model_data["parallel_mode"] = str(parallel_mode)
    islam.model_data["parallel_workers"] = int(parallel_workers)
    islam.model_data["output_path"] = str(output_path)
    os.makedirs(islam.output_path, exist_ok=True)


def collect_final_state(net) -> Dict[str, Dict[str, np.ndarray]]:
    """提取最终时刻各河道的关键状态量，用于和串行结果比较。"""
    state: Dict[str, Dict[str, np.ndarray]] = {}
    edge_items = sorted(
        net.G.edges(data=True),
        key=lambda item: (item[2].get("name", ""), item[0], item[1])
    )
    for u, v, data in edge_items:
        river = data["river"]
        river_name = data.get("name", f"{u}->{v}")
        n = int(river.cell_num)
        state[river_name] = {
            "water_level": np.asarray(river.water_level[1:n + 1], dtype=float).copy(),
            "water_depth": np.asarray(river.water_depth[1:n + 1], dtype=float).copy(),
            "Q": np.asarray(river.Q[1:n + 1], dtype=float).copy(),
            "U": np.asarray(river.U[1:n + 1], dtype=float).copy(),
        }
    return state


def run_single_case(label: str,
                    workers: int,
                    repeat_idx: int,
                    yield_step: float,
                    print_progress: bool,
                    export_graph: bool,
                    run_root: Path) -> Tuple[dict, Dict[str, Dict[str, np.ndarray]]]:
    parallel_mode = "process"
    case_dir = run_root / f"{label}_repeat_{repeat_idx:02d}"
    ensure_dir(case_dir)
    configure_runtime(parallel_workers=workers, output_path=case_dir, parallel_mode=parallel_mode)

    print(
        f"[Benchmark] case={label}, workers={workers}, repeat={repeat_idx} 开始 | "
        f"yield_step={yield_step}, print_progress={print_progress}",
        flush=True,
    )
    net = islam.build_net(export_graph=export_graph)
    t0 = time.perf_counter()
    for _ in net.Evolve(yield_step):
        if print_progress:
            net.print_evolve_info()
    wrapper_elapsed = time.perf_counter() - t0
    wall_elapsed = float(wrapper_elapsed)
    evolve_elapsed = float(getattr(net, "caculation_time", wrapper_elapsed))
    state = collect_final_state(net)
    print(
        f"[Benchmark] case={label}, workers={workers}, repeat={repeat_idx} 完成 | "
        f"wall={wall_elapsed:.6f}s, evolve={evolve_elapsed:.6f}s, rivers={len(state)}",
        flush=True,
    )
    row = {
        "case": label,
        "workers": int(workers),
        "repeat": int(repeat_idx),
        "wall_seconds": wall_elapsed,
        "evolve_seconds": evolve_elapsed,
        "wrapper_seconds": wrapper_elapsed,
        "is_serial_baseline": bool(label == "serial"),
        "output_path": str(case_dir),
    }
    return row, state


def compare_states(case: str,
                   workers: int,
                   repeat_idx: int,
                   baseline_state: Dict[str, Dict[str, np.ndarray]],
                   test_state: Dict[str, Dict[str, np.ndarray]]) -> Tuple[list[dict], dict]:
    """和串行基准逐河道逐变量比较。"""
    detail_rows: list[dict] = []
    max_abs_global = 0.0
    max_rmse_global = 0.0
    mean_abs_values = []
    compared_series = 0

    river_names = sorted(set(baseline_state) | set(test_state))
    for river_name in river_names:
        base_river = baseline_state.get(river_name)
        test_river = test_state.get(river_name)
        if base_river is None or test_river is None:
            detail_rows.append({
                "case": case,
                "workers": workers,
                "repeat": repeat_idx,
                "river": river_name,
                "variable": "<missing>",
                "count": 0,
                "max_abs_diff": np.nan,
                "mean_abs_diff": np.nan,
                "rmse": np.nan,
                "status": "missing_river",
            })
            continue

        for var in ["water_level", "water_depth", "Q", "U"]:
            a = np.asarray(base_river[var], dtype=float)
            b = np.asarray(test_river[var], dtype=float)
            if a.shape != b.shape:
                detail_rows.append({
                    "case": case,
                    "workers": workers,
                    "repeat": repeat_idx,
                    "river": river_name,
                    "variable": var,
                    "count": 0,
                    "max_abs_diff": np.nan,
                    "mean_abs_diff": np.nan,
                    "rmse": np.nan,
                    "status": f"shape_mismatch:{a.shape}!={b.shape}",
                })
                continue

            diff = b - a
            abs_diff = np.abs(diff)
            max_abs = float(abs_diff.max()) if abs_diff.size else 0.0
            mean_abs = float(abs_diff.mean()) if abs_diff.size else 0.0
            rmse = float(np.sqrt(np.mean(diff ** 2))) if diff.size else 0.0
            detail_rows.append({
                "case": case,
                "workers": workers,
                "repeat": repeat_idx,
                "river": river_name,
                "variable": var,
                "count": int(diff.size),
                "max_abs_diff": max_abs,
                "mean_abs_diff": mean_abs,
                "rmse": rmse,
                "status": "ok",
            })
            max_abs_global = max(max_abs_global, max_abs)
            max_rmse_global = max(max_rmse_global, rmse)
            mean_abs_values.append(mean_abs)
            compared_series += 1

    summary = {
        "case": case,
        "workers": workers,
        "repeat": repeat_idx,
        "compared_series": compared_series,
        "global_max_abs_diff": max_abs_global,
        "global_max_rmse": max_rmse_global,
        "global_mean_abs_diff": float(np.mean(mean_abs_values)) if mean_abs_values else np.nan,
    }
    return detail_rows, summary


def summarize_timing_results(raw_df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        raw_df.groupby(["case", "workers", "is_serial_baseline"], as_index=False)
        .agg(
            runs=("repeat", "count"),
            wall_mean=("wall_seconds", "mean"),
            wall_std=("wall_seconds", "std"),
            wall_min=("wall_seconds", "min"),
            wall_max=("wall_seconds", "max"),
            evolve_mean=("evolve_seconds", "mean"),
            evolve_std=("evolve_seconds", "std"),
            wrapper_mean=("wrapper_seconds", "mean"),
            wrapper_std=("wrapper_seconds", "std"),
        )
        .sort_values(["workers", "case"])
        .reset_index(drop=True)
    )
    for col in ["wall_std", "evolve_std", "wrapper_std"]:
        summary[col] = summary[col].fillna(0.0)

    baseline_row = summary.loc[summary["case"] == "serial"]
    if baseline_row.empty:
        baseline_row = summary.loc[summary["workers"] == summary["workers"].min()]
    baseline_wall = float(baseline_row["wall_mean"].iloc[0])
    baseline_evolve = float(baseline_row["evolve_mean"].iloc[0])

    summary["vs_serial_wall_speedup"] = baseline_wall / summary["wall_mean"]
    denom = summary["workers"].replace(0, 1)
    summary["vs_serial_wall_efficiency"] = summary["vs_serial_wall_speedup"] / denom
    summary.loc[summary["workers"] == 0, "vs_serial_wall_efficiency"] = 1.0

    summary["vs_serial_evolve_speedup"] = baseline_evolve / summary["evolve_mean"]
    summary["vs_serial_evolve_efficiency"] = summary["vs_serial_evolve_speedup"] / denom
    summary.loc[summary["workers"] == 0, "vs_serial_evolve_efficiency"] = 1.0

    summary["wall_delta_vs_prev"] = summary["wall_mean"].diff()
    summary["wall_pct_vs_prev"] = summary["wall_mean"].pct_change()
    return summary


def summarize_accuracy_results(acc_df: pd.DataFrame) -> pd.DataFrame:
    if acc_df.empty:
        return pd.DataFrame(columns=[
            "case", "workers", "runs", "global_max_abs_diff_mean",
            "global_max_rmse_mean", "global_mean_abs_diff_mean"
        ])
    summary = (
        acc_df.groupby(["case", "workers"], as_index=False)
        .agg(
            runs=("repeat", "count"),
            global_max_abs_diff_mean=("global_max_abs_diff", "mean"),
            global_max_abs_diff_max=("global_max_abs_diff", "max"),
            global_max_rmse_mean=("global_max_rmse", "mean"),
            global_max_rmse_max=("global_max_rmse", "max"),
            global_mean_abs_diff_mean=("global_mean_abs_diff", "mean"),
        )
        .sort_values(["workers", "case"])
        .reset_index(drop=True)
    )
    return summary


def save_plot_data(summary_df: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    plot_df = summary_df[[
        "case", "workers", "wall_mean", "wall_std",
        "vs_serial_wall_speedup", "vs_serial_wall_efficiency"
    ]].copy()
    plot_df.to_csv(output_dir / "wall_time_plot_data.csv", index=False, encoding="utf-8-sig")
    return plot_df


def save_plots(summary_df: pd.DataFrame, output_dir: Path) -> None:
    plot_df = summary_df.sort_values("workers").copy()
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    ax.errorbar(
        plot_df["workers"],
        plot_df["wall_mean"],
        yerr=plot_df["wall_std"],
        marker="o",
        capsize=4,
        linewidth=1.5,
        label="Wall time",
    )

    serial_df = plot_df[plot_df["case"] == "serial"]
    if not serial_df.empty:
        ax.scatter(serial_df["workers"], serial_df["wall_mean"], s=70, marker="s", label="Serial baseline")
        ax.axhline(float(serial_df["wall_mean"].iloc[0]), linestyle="--", linewidth=1.0, alpha=0.7)

    ax.set_xlabel("Process count")
    ax.set_ylabel("Wall time (s)")
    ax.set_title("Islam benchmark: wall time vs process count")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "wall_time_vs_workers.png", dpi=220)
    plt.close(fig)


def save_metadata(output_dir: Path, worker_values: list[int], repeats: int,
                  yield_step: float, print_progress: bool) -> None:
    payload = {
        "serial_baseline": SERIAL_BASELINE,
        "worker_values": worker_values,
        "repeats": repeats,
        "yield_step": yield_step,
        "print_progress_during_benchmark": print_progress,
        "parallel_mode": "process",
        "base_script": "Islam_gpt_hardcoded.py",
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }
    with open(output_dir / "benchmark_config.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def build_case_list(start: int, end: int, include_serial: bool) -> list[tuple[str, int]]:
    if start < 1 or end < start:
        raise ValueError("需要满足: 1 <= start <= end")
    cases: list[tuple[str, int]] = []
    if include_serial:
        cases.append(("serial", 0))
    for workers in range(start, end + 1):
        cases.append((f"process_{workers}", workers))
    return cases


def save_report(timing_summary_df: pd.DataFrame,
                accuracy_summary_df: pd.DataFrame,
                output_dir: Path,
                total_benchmark_seconds: float,
                case_list: list[tuple[str, int]],
                repeats: int,
                yield_step: float) -> None:
    best_row = timing_summary_df.loc[timing_summary_df["wall_mean"].idxmin()]
    serial_row = timing_summary_df.loc[timing_summary_df["case"] == "serial"]
    serial_wall = float(serial_row["wall_mean"].iloc[0]) if not serial_row.empty else None

    lines = [
        "# Islam benchmark summary",
        "",
        f"- Total benchmark time: {total_benchmark_seconds:.6f} s",
        f"- Tested cases: {case_list}",
        f"- Repeats per case: {repeats}",
        f"- Yield step: {yield_step}",
        "",
        "## Best wall-time configuration",
        "",
        f"- case: {best_row['case']}",
        f"- workers: {int(best_row['workers'])}",
        f"- wall_mean: {best_row['wall_mean']:.6f} s",
        f"- vs_serial_wall_speedup: {best_row['vs_serial_wall_speedup']:.6f}",
        f"- vs_serial_wall_efficiency: {best_row['vs_serial_wall_efficiency']:.6f}",
        "",
    ]
    if serial_wall is not None:
        lines.extend([
            "## Serial baseline",
            "",
            f"- serial wall_mean: {serial_wall:.6f} s",
            "",
        ])

    if not accuracy_summary_df.empty:
        lines.extend([
            "## Accuracy summary versus serial baseline",
            "",
            accuracy_summary_df.to_markdown(index=False),
            "",
        ])

    lines.extend([
        "## Timing summary table",
        "",
        timing_summary_df.to_markdown(index=False),
        "",
        "## Saved files",
        "",
        "- benchmark_raw_runs.csv: 原始逐次运行耗时数据",
        "- benchmark_summary.csv: 各配置耗时汇总",
        "- benchmark_accuracy_summary.csv: 与串行基准的误差汇总",
        "- benchmark_accuracy_details.csv: 逐河道逐变量误差明细",
        "- wall_time_plot_data.csv: 绘图原始数据",
        "- wall_time_vs_workers.png: 进程数-耗时图",
        "- benchmark_config.json: 本次基准配置",
        "",
    ])
    (output_dir / "benchmark_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Islam 河网 benchmark：包含非多进程基准、1~10 进程对比和结果一致性比较")
    parser.add_argument("--start", type=int, default=WORKER_START, help="起始进程数")
    parser.add_argument("--end", type=int, default=WORKER_END, help="结束进程数")
    parser.add_argument("--repeats", type=int, default=REPEATS, help="每个配置重复次数")
    parser.add_argument("--yield-step", type=float, default=YIELD_STEP, help="模型回报间隔(秒)")
    parser.add_argument("--print-progress", action="store_true", help="benchmark 运行时打印模型内部进度")
    parser.add_argument("--no-serial", action="store_true", help="不加入非多进程基准")
    args = parser.parse_args()

    if args.repeats < 1:
        raise ValueError("repeats 必须 >= 1")

    output_dir = OUTPUT_DIR
    run_root = TEMP_RUN_ROOT
    ensure_dir(output_dir)
    ensure_dir(run_root)

    include_serial = not args.no_serial
    case_list = build_case_list(args.start, args.end, include_serial=include_serial)

    t_bench0 = time.perf_counter()
    raw_rows: list[dict] = []
    acc_detail_rows: list[dict] = []
    acc_summary_rows: list[dict] = []
    baseline_state: Dict[str, Dict[str, np.ndarray]] | None = None

    for label, workers in case_list:
        for repeat_idx in range(1, args.repeats + 1):
            export_graph = EXPORT_GRAPH_ON_FIRST_RUN and not raw_rows
            row, state = run_single_case(
                label=label,
                workers=workers,
                repeat_idx=repeat_idx,
                yield_step=args.yield_step,
                print_progress=args.print_progress or PRINT_PROGRESS_DURING_BENCHMARK,
                export_graph=export_graph,
                run_root=run_root,
            )
            raw_rows.append(row)

            if label == "serial":
                if baseline_state is None:
                    baseline_state = state
                    acc_summary_rows.append({
                        "case": label,
                        "workers": workers,
                        "repeat": repeat_idx,
                        "compared_series": 0,
                        "global_max_abs_diff": 0.0,
                        "global_max_rmse": 0.0,
                        "global_mean_abs_diff": 0.0,
                    })
                else:
                    detail_rows, acc_summary = compare_states(label, workers, repeat_idx, baseline_state, state)
                    acc_detail_rows.extend(detail_rows)
                    acc_summary_rows.append(acc_summary)
            else:
                if baseline_state is None:
                    raise RuntimeError("需要先运行串行基准，才能进行结果一致性比较。")
                detail_rows, acc_summary = compare_states(label, workers, repeat_idx, baseline_state, state)
                acc_detail_rows.extend(detail_rows)
                acc_summary_rows.append(acc_summary)

    total_benchmark_seconds = time.perf_counter() - t_bench0

    raw_df = pd.DataFrame(raw_rows)
    timing_summary_df = summarize_timing_results(raw_df)
    acc_summary_df = summarize_accuracy_results(pd.DataFrame(acc_summary_rows))
    acc_detail_df = pd.DataFrame(acc_detail_rows)

    raw_df.to_csv(output_dir / "benchmark_raw_runs.csv", index=False, encoding="utf-8-sig")
    timing_summary_df.to_csv(output_dir / "benchmark_summary.csv", index=False, encoding="utf-8-sig")
    acc_summary_df.to_csv(output_dir / "benchmark_accuracy_summary.csv", index=False, encoding="utf-8-sig")
    acc_detail_df.to_csv(output_dir / "benchmark_accuracy_details.csv", index=False, encoding="utf-8-sig")

    save_plot_data(timing_summary_df, output_dir)
    save_plots(timing_summary_df, output_dir)
    save_metadata(output_dir, [w for _, w in case_list], args.repeats, args.yield_step, args.print_progress)
    save_report(timing_summary_df, acc_summary_df, output_dir, total_benchmark_seconds, case_list, args.repeats, args.yield_step)

    print("\n=== Benchmark 完成 ===", flush=True)
    print(f"结果目录: {output_dir}", flush=True)
    print(f"原始数据: {output_dir / 'benchmark_raw_runs.csv'}", flush=True)
    print(f"耗时汇总: {output_dir / 'benchmark_summary.csv'}", flush=True)
    print(f"误差汇总: {output_dir / 'benchmark_accuracy_summary.csv'}", flush=True)
    print(f"误差明细: {output_dir / 'benchmark_accuracy_details.csv'}", flush=True)
    print(f"图片: {output_dir / 'wall_time_vs_workers.png'}", flush=True)
    print(f"报告: {output_dir / 'benchmark_report.md'}", flush=True)


if __name__ == "__main__":
    main()
