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
    parser.add_argument("--perf-json", required=True)
    parser.add_argument("--profile-out", default=None)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--sim-end-time", required=True)
    parser.add_argument("--yield-step", type=float, default=1800.0)
    parser.add_argument("--print-progress", action="store_true")
    parser.add_argument("--use-cpp-evolve", action="store_true", default=False)
    parser.add_argument("--use-cython-nodechain", action="store_true", default=False)
    parser.add_argument("--use-cython-nodechain-direct-fast", action="store_true", default=False)
    parser.add_argument("--use-cython-nodechain-prebound-fast", action="store_true", default=False)
    parser.add_argument("--use-cpp-nodechain-deep-apply", action="store_true", default=False)
    parser.add_argument("--use-cpp-nodechain-commit-deep", action="store_true", default=False)
    parser.add_argument("--use-cython-roe-flux", action="store_true", default=False)
    parser.add_argument("--use-cpp-roe-flux-deep", action="store_true", default=False)
    parser.add_argument("--use-cpp-roe-flux-rect-deep", action="store_true", default=False)
    parser.add_argument("--use-cpp-update-cell", action="store_true", default=False)
    parser.add_argument("--use-cpp-assemble", action="store_true", default=False)
    parser.add_argument("--use-cpp-assemble-deep", action="store_true", default=False)
    parser.add_argument("--use-cpp-roe-matrix", action="store_true", default=False)
    parser.add_argument("--use-cpp-face-uc", action="store_true", default=False)
    parser.add_argument("--use-cpp-global-cfl-deep", action="store_true", default=False)
    args = parser.parse_args()

    os.environ["ISLAM_USE_PARALLEL"] = "0"
    os.environ["ISLAM_FAST_MODE"] = "0"
    os.environ["ISLAM_USE_CPP_EVOLVE"] = "1" if args.use_cpp_evolve else "0"
    os.environ["ISLAM_CPP_THREADS"] = "0"
    os.environ["ISLAM_USE_CYTHON_NODECHAIN"] = "1" if args.use_cython_nodechain else "0"
    os.environ["ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST"] = "1" if args.use_cython_nodechain_direct_fast else "0"
    os.environ["ISLAM_USE_CYTHON_NODECHAIN_PREBOUND_FAST"] = "1" if args.use_cython_nodechain_prebound_fast else "0"
    os.environ["ISLAM_CPP_USE_NODECHAIN_DEEP_APPLY"] = "1" if args.use_cpp_nodechain_deep_apply else "0"
    os.environ["ISLAM_CPP_USE_NODECHAIN_COMMIT_DEEP"] = "1" if args.use_cpp_nodechain_commit_deep else "0"
    os.environ["ISLAM_USE_CYTHON_ROE_FLUX"] = "1" if args.use_cython_roe_flux else "0"
    os.environ["ISLAM_CPP_USE_ROE_FLUX_DEEP"] = "1" if args.use_cpp_roe_flux_deep else "0"
    os.environ["ISLAM_CPP_USE_ROE_FLUX_RECT_DEEP"] = "1" if args.use_cpp_roe_flux_rect_deep else "0"
    os.environ["ISLAM_CPP_USE_UPDATE_CELL"] = "1" if args.use_cpp_update_cell else "0"
    os.environ["ISLAM_CPP_USE_ASSEMBLE"] = "1" if args.use_cpp_assemble else "0"
    os.environ["ISLAM_CPP_USE_ASSEMBLE_DEEP"] = "1" if args.use_cpp_assemble_deep else "0"
    os.environ["ISLAM_CPP_USE_ROE_MATRIX"] = "1" if args.use_cpp_roe_matrix else "0"
    os.environ["ISLAM_CPP_USE_FACE_UC"] = "1" if args.use_cpp_face_uc else "0"
    os.environ["ISLAM_CPP_USE_GLOBAL_CFL_DEEP"] = "1" if args.use_cpp_global_cfl_deep else "0"
    os.environ["ISLAM_OUTPUT_PATH"] = args.output_dir
    os.environ["ISLAM_SIM_END_TIME"] = args.sim_end_time
    os.environ["ISLAM_OUTPUT_RIVERS"] = "river11"
    os.environ["ISLAM_SAVE_CFL_HISTORY"] = "1"
    os.environ["ISLAM_PERF_PROFILE"] = "1"
    os.environ.setdefault("ISLAM_WARMUP_HOURS", "0.0")
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplconfig_cpp_exact")
    os.environ.setdefault("XDG_CACHE_HOME", "/tmp/xdg_cache_cpp_exact")

    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    Islam = importlib.import_module("Islam")

    net = Islam.build_net(export_png=False)
    Islam.maybe_run_warmup(net)
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
        "perf_json": str(Path(args.perf_json).resolve()),
        "profile_out": None if args.profile_out is None else str(Path(args.profile_out).resolve()),
        "model_time_seconds": float(net.caculation_time),
        "evolve_wall_time_seconds": float(evolve_wall),
        "step_count": int(net.step_count),
        "use_cpp_evolve": bool(args.use_cpp_evolve),
        "use_cython_nodechain": bool(args.use_cython_nodechain),
        "use_cython_nodechain_direct_fast": bool(args.use_cython_nodechain_direct_fast),
        "use_cython_nodechain_prebound_fast": bool(args.use_cython_nodechain_prebound_fast),
        "use_cpp_nodechain_deep_apply": bool(args.use_cpp_nodechain_deep_apply),
        "use_cpp_nodechain_commit_deep": bool(args.use_cpp_nodechain_commit_deep),
        "use_cython_roe_flux": bool(args.use_cython_roe_flux),
        "use_cpp_roe_flux_deep": bool(args.use_cpp_roe_flux_deep),
        "use_cpp_roe_flux_rect_deep": bool(args.use_cpp_roe_flux_rect_deep),
        "use_cpp_update_cell": bool(args.use_cpp_update_cell),
        "use_cpp_assemble": bool(args.use_cpp_assemble),
        "use_cpp_assemble_deep": bool(args.use_cpp_assemble_deep),
        "use_cpp_roe_matrix": bool(args.use_cpp_roe_matrix),
        "use_cpp_face_uc": bool(args.use_cpp_face_uc),
        "use_cpp_global_cfl_deep": bool(args.use_cpp_global_cfl_deep),
    }
    perf_stats = net.export_perf_stats() if hasattr(net, "export_perf_stats") else {}

    Path(args.summary_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.perf_json).write_text(json.dumps(perf_stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
