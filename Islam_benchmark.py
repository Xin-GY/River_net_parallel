import os

# ===== OpenMP / BLAS 线程控制（必须放在数值库导入之前） =====
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OMP_MAX_ACTIVE_LEVELS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("KMP_WARNINGS", "0")

import json
import time
from pathlib import Path
import argparse
import threading
from queue import Queue

import pandas as pd
import matplotlib.pyplot as plt

import Islam_gpt_hardcoded as islam

# =========================
# 可直接修改的基准配置
# =========================
WORKER_START = 1
WORKER_END = 10
REPEATS = 1
YIELD_STEP = 300.0
PRINT_PROGRESS_DURING_BENCHMARK = False
HEARTBEAT_SECONDS = 10.0
EXPORT_GRAPH_ON_FIRST_RUN = False
OUTPUT_DIR = Path("result/Islam_benchmark")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _run_once_with_heartbeat(*, yield_step: float, export_graph: bool, print_progress: bool, heartbeat_seconds: float, case_label: str):
    q: Queue = Queue()

    def worker():
        try:
            result = islam.run_once(
                yield_step=yield_step,
                export_graph=export_graph,
                print_progress=print_progress,
            )
            q.put(("ok", result))
        except Exception as e:  # pragma: no cover
            q.put(("err", e))

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    start = time.perf_counter()
    if heartbeat_seconds and heartbeat_seconds > 0:
        while t.is_alive():
            t.join(timeout=heartbeat_seconds)
            if t.is_alive():
                elapsed = time.perf_counter() - start
                print(f"[Heartbeat] {case_label} 仍在运行 | wall_elapsed={elapsed:.1f}s", flush=True)
    else:
        t.join()

    status, payload = q.get()
    if status == "err":
        raise payload
    return payload


def run_single_case(workers: int, repeat_idx: int, yield_step: float, print_progress: bool, export_graph: bool, heartbeat_seconds: float) -> dict:
    islam.PARALLEL_WORKERS = int(workers)
    if hasattr(islam, 'model_data'):
        islam.model_data['parallel_workers'] = int(workers)
        islam.model_data['parallel_mode'] = 'process'
        islam.model_data['progress_yield_step'] = float(yield_step)
        islam.model_data['print_progress'] = bool(print_progress)

    case_label = f"workers={workers}, repeat={repeat_idx}"
    print(
        f"[Benchmark] {case_label} 开始 | yield_step={yield_step}, print_progress={print_progress}, heartbeat={heartbeat_seconds}",
        flush=True,
    )
    t0 = time.perf_counter()
    wall_elapsed, evolve_elapsed = _run_once_with_heartbeat(
        yield_step=yield_step,
        export_graph=export_graph,
        print_progress=print_progress,
        heartbeat_seconds=heartbeat_seconds,
        case_label=case_label,
    )
    total_elapsed = time.perf_counter() - t0
    print(
        f"[Benchmark] {case_label} 完成 | wall={wall_elapsed:.6f}s, evolve={evolve_elapsed:.6f}s, total_wrapper={total_elapsed:.6f}s",
        flush=True,
    )
    return {
        'workers': int(workers),
        'repeat': int(repeat_idx),
        'wall_seconds': float(wall_elapsed),
        'evolve_seconds': float(evolve_elapsed),
        'wrapper_seconds': float(total_elapsed),
    }


def summarize_results(raw_df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        raw_df.groupby('workers', as_index=False)
        .agg(
            runs=('repeat', 'count'),
            wall_mean=('wall_seconds', 'mean'),
            wall_std=('wall_seconds', 'std'),
            wall_min=('wall_seconds', 'min'),
            wall_max=('wall_seconds', 'max'),
            evolve_mean=('evolve_seconds', 'mean'),
            evolve_std=('evolve_seconds', 'std'),
            wrapper_mean=('wrapper_seconds', 'mean'),
            wrapper_std=('wrapper_seconds', 'std'),
        )
        .sort_values('workers')
        .reset_index(drop=True)
    )

    for col in ['wall_std', 'evolve_std', 'wrapper_std']:
        summary[col] = summary[col].fillna(0.0)

    baseline_wall = float(summary.loc[summary['workers'] == summary['workers'].min(), 'wall_mean'].iloc[0])
    baseline_evolve = float(summary.loc[summary['workers'] == summary['workers'].min(), 'evolve_mean'].iloc[0])

    summary['wall_speedup'] = baseline_wall / summary['wall_mean']
    summary['wall_efficiency'] = summary['wall_speedup'] / summary['workers']
    summary['evolve_speedup'] = baseline_evolve / summary['evolve_mean']
    summary['evolve_efficiency'] = summary['evolve_speedup'] / summary['workers']
    return summary


def save_plots(summary_df: pd.DataFrame, output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(
        summary_df['workers'],
        summary_df['wall_mean'],
        yerr=summary_df['wall_std'],
        marker='o',
        capsize=4,
        label='Wall time',
    )
    ax.set_xlabel('Process count')
    ax.set_ylabel('Time (s)')
    ax.set_title('Islam benchmark: wall time vs process count')
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / 'wall_time_vs_workers.png', dpi=200)
    plt.close(fig)


def save_metadata(output_dir: Path, worker_values: list[int], repeats: int, yield_step: float, print_progress: bool, heartbeat_seconds: float) -> None:
    payload = {
        'worker_values': worker_values,
        'repeats': repeats,
        'yield_step': yield_step,
        'print_progress_during_benchmark': print_progress,
        'heartbeat_seconds': heartbeat_seconds,
        'parallel_mode': 'process',
        'base_script': 'Islam_gpt_hardcoded.py',
    }
    with open(output_dir / 'benchmark_config.json', 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description='Islam 河网多进程 benchmark (1~10 processes by default)')
    parser.add_argument('--start', type=int, default=WORKER_START, help='起始进程数')
    parser.add_argument('--end', type=int, default=WORKER_END, help='结束进程数')
    parser.add_argument('--repeats', type=int, default=REPEATS, help='每个进程数重复次数')
    parser.add_argument('--yield-step', type=float, default=YIELD_STEP, help='模型回报间隔(模拟秒)')
    parser.add_argument('--print-progress', action='store_true', help='benchmark 运行时打印模型内部进度')
    parser.add_argument('--heartbeat-seconds', type=float, default=HEARTBEAT_SECONDS, help='墙钟心跳输出间隔；<=0 表示关闭')
    args = parser.parse_args()

    if args.start < 1 or args.end < args.start:
        raise ValueError('需要满足: 1 <= start <= end')
    if args.repeats < 1:
        raise ValueError('repeats 必须 >= 1')

    worker_values = list(range(args.start, args.end + 1))

    ensure_dir(OUTPUT_DIR)
    save_metadata(
        OUTPUT_DIR,
        worker_values=worker_values,
        repeats=args.repeats,
        yield_step=args.yield_step,
        print_progress=args.print_progress or PRINT_PROGRESS_DURING_BENCHMARK,
        heartbeat_seconds=args.heartbeat_seconds,
    )

    print(
        f"开始 benchmark: workers={worker_values}, repeats={args.repeats}, "
        f"yield_step={args.yield_step}, print_progress={args.print_progress or PRINT_PROGRESS_DURING_BENCHMARK}, heartbeat_seconds={args.heartbeat_seconds}, output_dir={OUTPUT_DIR}",
        flush=True,
    )

    rows = []
    global_start = time.perf_counter()
    first_run = True
    for workers in worker_values:
        for repeat_idx in range(1, args.repeats + 1):
            row = run_single_case(
                workers=workers,
                repeat_idx=repeat_idx,
                yield_step=args.yield_step,
                print_progress=args.print_progress or PRINT_PROGRESS_DURING_BENCHMARK,
                export_graph=(EXPORT_GRAPH_ON_FIRST_RUN and first_run),
                heartbeat_seconds=args.heartbeat_seconds,
            )
            rows.append(row)
            pd.DataFrame(rows).to_csv(OUTPUT_DIR / 'benchmark_raw_runs.csv', index=False, encoding='utf-8-sig')
            first_run = False

    total_benchmark_seconds = time.perf_counter() - global_start
    raw_df = pd.DataFrame(rows)
    summary_df = summarize_results(raw_df)
    summary_df.to_csv(OUTPUT_DIR / 'benchmark_summary.csv', index=False, encoding='utf-8-sig')
    save_plots(summary_df, OUTPUT_DIR)
    summary_df[['workers', 'wall_mean', 'wall_std']].to_csv(OUTPUT_DIR / 'wall_time_plot_data.csv', index=False, encoding='utf-8-sig')

    best_row = summary_df.loc[summary_df['wall_mean'].idxmin()]
    md_lines = [
        '# Islam benchmark summary',
        '',
        f'- Total benchmark time: {total_benchmark_seconds:.6f} s',
        f'- Tested workers: {worker_values}',
        f'- Repeats per worker: {args.repeats}',
        f'- Yield step: {args.yield_step}',
        f'- Print progress: {args.print_progress or PRINT_PROGRESS_DURING_BENCHMARK}',
        f'- Heartbeat seconds: {args.heartbeat_seconds}',
        '',
        '## Best wall-time configuration',
        '',
        f"- workers: {int(best_row['workers'])}",
        f"- wall_mean: {best_row['wall_mean']:.6f} s",
        f"- wall_speedup: {best_row['wall_speedup']:.6f}",
        f"- wall_efficiency: {best_row['wall_efficiency']:.6f}",
        '',
        '## Summary table',
        '',
        summary_df.to_markdown(index=False),
        '',
    ]
    (OUTPUT_DIR / 'benchmark_report.md').write_text('\n'.join(md_lines), encoding='utf-8')


if __name__ == '__main__':
    main()
