#!/usr/bin/env python3
import argparse
import cProfile
import importlib
import json
import os
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-name", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--profile-out", default=None)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--sim-end-time", required=True)
    parser.add_argument("--yield-step", type=float, default=1800.0)
    parser.add_argument("--print-progress", action="store_true")
    args = parser.parse_args()

    os.environ["ISLAM_USE_PARALLEL"] = "0"
    os.environ["ISLAM_FAST_MODE"] = "0"
    os.environ["ISLAM_OUTPUT_PATH"] = args.output_dir
    os.environ["ISLAM_SIM_END_TIME"] = args.sim_end_time
    os.environ["ISLAM_OUTPUT_RIVERS"] = "river11"
    os.environ["ISLAM_SAVE_CFL_HISTORY"] = "1"
    os.environ.setdefault("ISLAM_WARMUP_HOURS", "0.0")
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplconfig_cython_exact")
    os.environ.setdefault("XDG_CACHE_HOME", "/tmp/xdg_cache_cython_exact")

    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    Islam = importlib.import_module("Islam")

    net = Islam.build_net(export_png=False)
    warm = Islam.maybe_run_warmup(net)
    Islam.prepare_net_for_evolve(net, yield_step=args.yield_step)

    profiler = cProfile.Profile() if args.profile_out else None
    start = time.perf_counter()
    if profiler is not None:
        profiler.enable()
    Islam.run_prepared_evolve(net, yield_step=args.yield_step, print_progress=args.print_progress)
    if profiler is not None:
        profiler.disable()
    evolve_wall = time.perf_counter() - start

    if profiler is not None:
        profiler.dump_stats(args.profile_out)

    summary = {
        "case_name": args.case_name,
        "cwd": str(repo_root),
        "output_dir": str(Path(args.output_dir).resolve()),
        "summary_json": str(Path(args.summary_json).resolve()),
        "profile_out": None if args.profile_out is None else str(Path(args.profile_out).resolve()),
        "model_time_seconds": float(net.caculation_time),
        "evolve_wall_time_seconds": float(evolve_wall),
        "step_count": int(net.step_count),
        "warmup_used": warm is not None,
    }
    Path(args.summary_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
