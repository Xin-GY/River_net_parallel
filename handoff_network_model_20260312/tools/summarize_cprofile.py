#!/usr/bin/env python3
import argparse
import json
import pstats
from pathlib import Path


def normalize_entry(func, stat):
    filename, lineno, funcname = func
    cc, nc, tt, ct, callers = stat
    return {
        "filename": filename,
        "lineno": lineno,
        "funcname": funcname,
        "primitive_calls": cc,
        "total_calls": nc,
        "tottime": tt,
        "cumtime": ct,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()

    stats = pstats.Stats(args.profile)
    project_root = str(Path(args.project_root).resolve())

    rows = []
    for func, stat in stats.stats.items():
        row = normalize_entry(func, stat)
        if project_root not in str(Path(row["filename"]).resolve()):
            continue
        rows.append(row)

    rows.sort(key=lambda x: x["cumtime"], reverse=True)
    payload = {
        "profile": str(Path(args.profile).resolve()),
        "project_root": project_root,
        "top": rows[: args.top],
        "all_rows": rows,
    }
    Path(args.json_out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["top"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
