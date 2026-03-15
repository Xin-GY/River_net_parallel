# FAST Preflight

## Goal Shift

This line now treats `40h full case -> as close to 30 s as possible` as the primary objective. Default exact preservation remains a constraint, but only a light smoke check is required unless a FAST change clearly leaks into the exact path.

## Current Protected State

- active worktree: `/tmp/overnight_fast_mode_30s`
- active branch: `fast-mode-30s`
- current HEAD: `1901e06`
- dirty runtime/code changes are preserved by:
  - `reports/fast_preflight_git_status.txt`
  - `reports/fast_preflight_worktree.diff`
  - `reports/fast_preflight_index.diff`

## Safety Checkpoints

- safety branch: `safety_fast_20260315_194332`
- safety worktree: `/tmp/fast_mode_safety_20260315_194332`

These checkpoints capture the current committed base. The dirty delta is recoverable from the exported diff files above.

## Current Dirty Inventory

- `Islam.py`
  - FAST adaptive environment wiring
- `Rivernet.py`
  - limiter-aware FAST adaptive gating
  - adaptive counters and run-summary fields
- `river_for_net.py`
  - dt-limiter origin tagging on river boundaries
- `tools/evaluate_fast_mode.py`
  - richer speed/volume/report handling for FAST comparisons
- `reports/*.md` / `reports/*.json`
  - adaptive 10-minute and 40-hour evaluation artifacts

## Destructive Actions

No destructive operation has been applied to the dirty FAST worktree. The line is safe to continue from.
