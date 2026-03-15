# FAST Branch Layout

## Primary FAST Line

- branch: `fast-mode-30s`
- worktree: `/tmp/overnight_fast_mode_30s`
- role:
  - keep FAST infrastructure
  - run sweep/adaptive/structural FAST experiments
  - only use smoke-level exact validation

## Safety Line

- branch: `safety_fast_20260315_194332`
- worktree: `/tmp/fast_mode_safety_20260315_194332`
- role:
  - immutable checkpoint for the current FAST base plus recoverable dirty delta

## Reference Lines

- `main` at `/home/xin/River_net_parallel`
  - protected repository entry point
- `exact-baseline-clean` at `/tmp/overnight_exact_baseline_clean`
  - used as reference for reports and accepted exact artifacts when needed
- `fast_mode_snapshot_20260314` at `/tmp/overnight_fast_snapshot`
  - preserved historical FAST snapshot

## Carry-In Policy

- keep:
  - FAST adaptive infrastructure
  - `tools/evaluate_fast_mode.py`
  - FAST error/speed reports
- do not prioritize:
  - repeated full exact strict compare loops
  - exact-only orchestration experiments already shown to have low value

## Validation Policy

- exact:
  - smoke only unless a FAST change plausibly leaks into default exact
- FAST:
  - 40-hour wall-clock + error report are the main decision criteria
