#!/usr/bin/env python3
import argparse
import atexit
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import time
from pathlib import Path


PY311 = Path("/home/xin/miniconda3/envs/python311/bin/python")
REPO_ROOT = Path("/home/xin/River_net_parallel")
EXACT_WORKTREE = Path("/tmp/overnight_exact_baseline_clean/handoff_network_model_20260312")
REF_WORKTREE = Path("/tmp/overnight_dea3202_ref/handoff_network_model_20260312")
REPORT_ROOT = EXACT_WORKTREE / "reports"
RUN_ROOT = REPORT_ROOT / "hotpath_runs"

ENV_BASE = {
    "MPLCONFIGDIR": "/tmp/mplconfig",
    "ISLAM_OUTPUT_RIVERS": "river11",
    "ISLAM_USE_FINE_INTERPOLATION": "0",
    "ISLAM_SAVE_RUN_SUMMARY": "1",
    "ISLAM_SAVE_CFL_HISTORY": "0",
}

HOT_TARGETS = {
    "boundary_updater": ("Rivernet", "_update_boundary_conditions_parallel"),
    "Caculate_face_U_C": ("River", "Caculate_face_U_C"),
    "Caculate_Roe_matrix": ("River", "Caculate_Roe_matrix"),
    "Caculate_Roe_Flux_2": ("River", "Caculate_Roe_Flux_2"),
    "Assemble_Flux_2": ("River", "Assemble_Flux_2"),
    "Update_cell_proprity2": ("River", "Update_cell_proprity2"),
}

_HOTPATH_METRICS = {name: {"calls": 0, "time_s": 0.0} for name in HOT_TARGETS}
_HOTPATH_ENABLED = False


def parse_model_runtime(stdout_text: str):
    step_match = re.search(r"共计算\s*(\d+)\s*步", stdout_text)
    time_match = re.search(r"总耗时:\s*([0-9.]+)\s*秒", stdout_text)
    return {
        "step_count": int(step_match.group(1)) if step_match else None,
        "model_time_s": float(time_match.group(1)) if time_match else None,
    }


def wrap_method(cls, method_name, label):
    original = getattr(cls, method_name)

    def wrapped(self, *args, **kwargs):
        t0 = time.perf_counter()
        try:
            return original(self, *args, **kwargs)
        finally:
            metric = _HOTPATH_METRICS[label]
            metric["calls"] += 1
            metric["time_s"] += time.perf_counter() - t0

    wrapped.__name__ = getattr(original, "__name__", method_name)
    wrapped.__qualname__ = getattr(original, "__qualname__", method_name)
    setattr(cls, method_name, wrapped)


def install_wrappers(project_root: Path):
    global _HOTPATH_ENABLED
    if _HOTPATH_ENABLED:
        return
    sys.path.insert(0, str(project_root))
    from Rivernet import Rivernet  # pylint: disable=import-outside-toplevel
    from river_for_net import River  # pylint: disable=import-outside-toplevel

    cls_map = {"Rivernet": Rivernet, "River": River}
    for label, (cls_name, method_name) in HOT_TARGETS.items():
        wrap_method(cls_map[cls_name], method_name, label)
    _HOTPATH_ENABLED = True


def write_process_metrics(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"hotpath_pid_{os.getpid()}.json"
    payload = {
        "pid": os.getpid(),
        "metrics": _HOTPATH_METRICS,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_env(mode: str):
    env = dict(ENV_BASE)
    if mode == "parallel":
        env.update(
            {
                "ISLAM_USE_PARALLEL": "1",
                "ISLAM_PARALLEL_BACKEND": "process",
                "ISLAM_PARALLEL_START_METHOD": "fork",
                "ISLAM_N_WORKERS": "4",
            }
        )
    else:
        env["ISLAM_USE_PARALLEL"] = "0"
    return env


def run_profile_once(args):
    project_root = Path(args.project_root).resolve()
    hotpath_dir = Path(args.hotpath_dir).resolve()
    result_dir = project_root / args.output_path
    if result_dir.exists():
        shutil.rmtree(result_dir)
    hotpath_dir.mkdir(parents=True, exist_ok=True)
    for old in hotpath_dir.glob("hotpath_pid_*.json"):
        old.unlink()

    install_wrappers(project_root)
    atexit.register(write_process_metrics, hotpath_dir)

    env = os.environ.copy()
    env.update(build_env(args.mode))
    env["ISLAM_OUTPUT_PATH"] = args.output_path
    env["ISLAM_SIM_END_TIME"] = args.sim_end_time
    os.environ.update(env)
    cwd = os.getcwd()
    try:
        os.chdir(project_root)
        runpy.run_path(str(project_root / "Islam.py"), run_name="__main__")
    finally:
        os.chdir(cwd)


def aggregate_hotpath_dir(hotpath_dir: Path):
    totals = {name: {"calls": 0, "time_s": 0.0} for name in HOT_TARGETS}
    files = sorted(hotpath_dir.glob("hotpath_pid_*.json"))
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for name, metric in payload.get("metrics", {}).items():
            if name not in totals:
                continue
            totals[name]["calls"] += int(metric.get("calls", 0))
            totals[name]["time_s"] += float(metric.get("time_s", 0.0))
    for metric in totals.values():
        calls = metric["calls"]
        metric["per_call_ms"] = (metric["time_s"] * 1000.0 / calls) if calls else 0.0
    return {"process_files": len(files), "metrics": totals}


def as_md_table(rows):
    if not rows:
        return "_none_"
    headers = list(rows[0].keys())
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(row[h]) for h in headers) + " |")
    return "\n".join(out)


def build_code_diff_summary():
    cmd = [
        "git",
        "-C",
        str(EXACT_WORKTREE.parent),
        "diff",
        "--unified=0",
        "dea3202",
        "--",
        "handoff_network_model_20260312/Rivernet.py",
        "handoff_network_model_20260312/river_for_net.py",
        "handoff_network_model_20260312/parallel_river_pool.py",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    diff_text = proc.stdout
    target_names = [
        "Caculate_face_U_C",
        "Caculate_Roe_matrix",
        "Caculate_Roe_Flux_2",
        "Assemble_Flux_2",
        "Update_cell_proprity2",
        "_update_boundary_conditions_parallel",
    ]
    touched_targets = [name for name in target_names if name in diff_text]
    return {
        "parallel_river_pool_identical": "parallel_river_pool.py" not in diff_text,
        "touched_targets": touched_targets,
        "summary_lines": [
            "Current exact branch adds run-summary and dt-limiter profiling scaffolding around evolve/CFL bookkeeping.",
            "Current exact branch annotates river boundary roles during topology classification.",
            "No diff hunk lands inside the listed hot river kernels or the default parallel boundary updater path." if not touched_targets else f"Diff text references target functions: {', '.join(touched_targets)}",
            "parallel_river_pool.py is unchanged relative to dea3202." if "parallel_river_pool.py" not in diff_text else "parallel_river_pool.py differs from dea3202.",
        ],
    }


def run_target(label: str, project_root: Path, sim_end_time: str, mode: str):
    run_dir = RUN_ROOT / f"{label}_{mode}"
    hotpath_dir = run_dir / "hotpath"
    log_path = run_dir / "stdout.log"
    json_path = run_dir / "summary.json"
    stats_result_path = f"result/{run_dir.name}_model_output"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(PY311),
        str(Path(__file__).resolve()),
        "run-once",
        "--project-root",
        str(project_root),
        "--hotpath-dir",
        str(hotpath_dir),
        "--output-path",
        stats_result_path,
        "--sim-end-time",
        sim_end_time,
        "--mode",
        mode,
    ]
    env = os.environ.copy()
    env.update(build_env(mode))
    t0 = time.time()
    proc = subprocess.run(
        cmd,
        cwd=str(project_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    wall = time.time() - t0
    log_path.write_text(proc.stdout + "\n\n[stderr]\n" + proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"{label} failed with code {proc.returncode}; see {log_path}")

    runtime = parse_model_runtime(proc.stdout)
    aggregate = aggregate_hotpath_dir(hotpath_dir)
    payload = {
        "label": label,
        "mode": mode,
        "project_root": str(project_root),
        "wall_time_s": wall,
        "model_time_s": runtime["model_time_s"],
        "step_count": runtime["step_count"],
        "process_files": aggregate["process_files"],
        "metrics": aggregate["metrics"],
        "stdout_log": str(log_path),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def build_rows(current_payload, ref_payload, names):
    rows = []
    for name in names:
        cur = current_payload["metrics"][name]
        ref = ref_payload["metrics"][name]
        rows.append(
            {
                "function": name,
                "current_calls": cur["calls"],
                "ref_calls": ref["calls"],
                "current_time_s": f"{cur['time_s']:.6f}",
                "ref_time_s": f"{ref['time_s']:.6f}",
                "delta_time_s": f"{cur['time_s'] - ref['time_s']:.6f}",
                "current_per_call_ms": f"{cur['per_call_ms']:.6f}",
                "ref_per_call_ms": f"{ref['per_call_ms']:.6f}",
                "delta_per_call_ms": f"{cur['per_call_ms'] - ref['per_call_ms']:.6f}",
            }
        )
    return rows


def write_compare_report(par_current, par_ref, ser_current, ser_ref, report_md: Path, report_json: Path):
    code_summary = build_code_diff_summary()
    boundary_rows = build_rows(par_current, par_ref, ["boundary_updater"])
    kernel_rows = build_rows(
        ser_current,
        ser_ref,
        [
            "Caculate_face_U_C",
            "Caculate_Roe_matrix",
            "Caculate_Roe_Flux_2",
            "Assemble_Flux_2",
            "Update_cell_proprity2",
        ],
    )

    summary_rows = [
        {
            "run": "current_exact_parallel",
            "wall_time_s": f"{par_current['wall_time_s']:.6f}",
            "model_time_s": par_current["model_time_s"],
            "step_count": par_current["step_count"],
            "process_files": par_current["process_files"],
        },
        {
            "run": "dea3202_ref_parallel",
            "wall_time_s": f"{par_ref['wall_time_s']:.6f}",
            "model_time_s": par_ref["model_time_s"],
            "step_count": par_ref["step_count"],
            "process_files": par_ref["process_files"],
        },
        {
            "run": "current_exact_serial",
            "wall_time_s": f"{ser_current['wall_time_s']:.6f}",
            "model_time_s": ser_current["model_time_s"],
            "step_count": ser_current["step_count"],
            "process_files": ser_current["process_files"],
        },
        {
            "run": "dea3202_ref_serial",
            "wall_time_s": f"{ser_ref['wall_time_s']:.6f}",
            "model_time_s": ser_ref["model_time_s"],
            "step_count": ser_ref["step_count"],
            "process_files": ser_ref["process_files"],
        },
    ]

    report = {
        "parallel_current": par_current,
        "parallel_reference": par_ref,
        "serial_current": ser_current,
        "serial_reference": ser_ref,
        "boundary_rows": boundary_rows,
        "kernel_rows": kernel_rows,
        "code_diff_summary": code_summary,
    }
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Hotpath Diff vs dea3202",
        "",
        "## Run Summary",
        "",
        as_md_table(summary_rows),
        "",
        "## boundary_updater (default parallel exact)",
        "",
        as_md_table(boundary_rows),
        "",
        "## Local River Kernels (serial isolation run)",
        "",
        as_md_table(kernel_rows),
        "",
        "## Code Diff Summary",
        "",
    ]
    for line in code_summary["summary_lines"]:
        lines.append(f"- {line}")
    lines.extend(
        [
            "",
        "## Notes",
        "",
        "- `boundary_updater` is measured on the default exact parallel process backend with `fork`.",
        "- Worker-side river kernels are isolated with a serial 10-minute run so the wrapper timing stays in-process and comparable across worktrees.",
        "- Output paths are isolated under each worktree's `result/` tree; raw stdout/stderr logs are stored beside the JSON summaries.",
        "- A positive `delta_*` means the current exact line is slower than raw `dea3202` on the same 10-minute case.",
        "",
        ]
    )
    report_md.write_text("\n".join(lines), encoding="utf-8")


def compare_mode(args):
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    par_current = run_target("current_exact", EXACT_WORKTREE, args.sim_end_time, "parallel")
    par_reference = run_target("dea3202_ref", REF_WORKTREE, args.sim_end_time, "parallel")
    ser_current = run_target("current_exact", EXACT_WORKTREE, args.sim_end_time, "serial")
    ser_reference = run_target("dea3202_ref", REF_WORKTREE, args.sim_end_time, "serial")
    report_md = REPORT_ROOT / "hotpath_diff_vs_dea3202.md"
    report_json = REPORT_ROOT / "hotpath_diff_vs_dea3202.json"
    write_compare_report(par_current, par_reference, ser_current, ser_reference, report_md, report_json)
    print(str(report_md))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run-once")
    p_run.add_argument("--project-root", required=True)
    p_run.add_argument("--hotpath-dir", required=True)
    p_run.add_argument("--output-path", required=True)
    p_run.add_argument("--sim-end-time", required=True)
    p_run.add_argument("--mode", choices=("parallel", "serial"), required=True)

    p_compare = sub.add_parser("compare")
    p_compare.add_argument("--sim-end-time", default="2024-01-01 00:10:00")

    args = parser.parse_args()
    if args.cmd == "run-once":
        run_profile_once(args)
    else:
        compare_mode(args)


if __name__ == "__main__":
    main()
