#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


TOTAL_RE = re.compile(r"总耗时:\s*([0-9]+(?:\.[0-9]+)?)\s*秒")
STEP_RE = re.compile(r"共计算\s*([0-9]+)\s*步")


def parse_metrics(text: str) -> dict:
    total_matches = TOTAL_RE.findall(text)
    step_matches = STEP_RE.findall(text)
    model_time = float(total_matches[-1]) if total_matches else None
    step_count = int(step_matches[-1]) if step_matches else None
    return {
        "model_time_seconds": model_time,
        "step_count": step_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-name", required=True)
    parser.add_argument("--sim-end-time", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--stdout-log", required=True)
    parser.add_argument("--profile-out", default=None)
    parser.add_argument("--script", default="Islam.py")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stdout_log = Path(args.stdout_log)
    stdout_log.parent.mkdir(parents=True, exist_ok=True)
    summary_json = Path(args.summary_json)
    summary_json.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.update(
        {
            "ISLAM_USE_PARALLEL": "0",
            "ISLAM_FAST_MODE": "0",
            "ISLAM_OUTPUT_PATH": str(output_dir),
            "ISLAM_SIM_END_TIME": args.sim_end_time,
            "ISLAM_OUTPUT_RIVERS": "river11",
            "ISLAM_SAVE_CFL_HISTORY": "1",
            "ISLAM_WARMUP_HOURS": env.get("ISLAM_WARMUP_HOURS", "0.0"),
            "MPLCONFIGDIR": env.get("MPLCONFIGDIR", "/tmp/mplconfig_cython_exact"),
            "XDG_CACHE_HOME": env.get("XDG_CACHE_HOME", "/tmp/xdg_cache_cython_exact"),
        }
    )

    cmd = [sys.executable]
    if args.profile_out:
        profile_path = Path(args.profile_out)
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        cmd.extend(["-m", "cProfile", "-o", str(profile_path)])
    cmd.append(args.script)

    start = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
    )
    wall = time.perf_counter() - start

    combined = proc.stdout
    if proc.stderr:
        combined = combined + ("\n" if combined else "") + proc.stderr
    stdout_log.write_text(combined, encoding="utf-8")

    metrics = parse_metrics(combined)
    summary = {
        "case_name": args.case_name,
        "command": cmd,
        "cwd": str(repo_root),
        "output_dir": str(output_dir),
        "stdout_log": str(stdout_log),
        "returncode": proc.returncode,
        "wall_time_seconds": wall,
        **metrics,
    }
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
