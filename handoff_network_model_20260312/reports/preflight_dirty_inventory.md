# Preflight Dirty Inventory

Timestamp: 2026-03-14 22:34:14 +08:00

## Current Main Worktree

`main` at `dea3202` is currently clean: no unstaged or staged changes are present in `/home/xin/River_net_parallel`.

The previously dirty experimental work has already been preserved in two recoverable locations:

- snapshot branch: `fast_mode_snapshot_20260314` at `4cf4721`
- filesystem backup: `/tmp/fastmode_backup`

This inventory therefore summarizes the preserved experimental delta relative to `main`, so the prior work remains auditable and recoverable before any new overnight work starts.

## File-Level Inventory

### `handoff_network_model_20260312/Islam.py`

- Added isolated FAST_MODE environment parsing and runtime switches.
- Added optional run-summary and lighter-output controls used by FAST experiments.
- Added benchmark-oriented knobs for fast CFL / fast dt growth experiments.

### `handoff_network_model_20260312/Rivernet.py`

- Added exact-orchestration profiling and audit support from earlier experiments.
- Added FAST_MODE gating, internal-node-history save controls, and run-summary plumbing.
- Added multiple experimental internal-node backends and node-solve controls that were not accepted into the default exact path.

### `handoff_network_model_20260312/parallel_river_pool.py`

- Added worker-side experimental exact fused node-evaluation commands.
- Added compact payload and alternative aggregate-return paths for node solving.
- Added FAST/experimental worker command variants not present in accepted exact baseline.

### `handoff_network_model_20260312/river_for_net.py`

- Added response-table and predictor-oriented FAST node-solve experiments.
- Added extra profiling hooks and exact experimental hot-path variants.
- Added boundary / node-solve helper branches beyond the accepted baseline implementation.

### `handoff_network_model_20260312/tools/evaluate_fast_mode.py`

- New standalone FAST_MODE evaluation script for wall-clock and error metrics against accepted exact results.

## Recoverability

The preserved experimental state can be restored from either:

- `git switch fast_mode_snapshot_20260314`
- `/tmp/fastmode_backup/*.work`

No destructive cleanup was performed before creating these recovery points.
