# Branch Layout

Timestamp: 2026-03-14 22:34:14 +08:00

## Accepted Baseline

- baseline commit: `dea3202`
- baseline meaning: accepted exact implementation and current default reference for performance and strict-compare checks

## Safety / Recovery

- `main`
  - worktree: `/home/xin/River_net_parallel`
  - current HEAD: `dea3202`
  - role: stable coordination root
- `safety_main_20260314_223414`
  - start point: `dea3202`
  - role: non-destructive safety checkpoint created before overnight changes
- `fast_mode_snapshot_20260314`
  - start point: preserved experimental snapshot
  - current HEAD: `4cf4721`
  - role: recover prior FAST_MODE and mixed experimental work without polluting the exact line

## Overnight Working Lines

### `exact-baseline-clean`

- branch root: `dea3202`
- worktree: `/tmp/overnight_exact_baseline_clean`
- purpose: exact-only line
- allowed content:
  - safe profiling / timing / benchmark scaffolding
  - exact-only kernel work that preserves strict equality
- excluded content:
  - FAST_MODE approximations
  - response-table shortcuts
  - q_hint / predictor approximations
  - previously rejected exact fused-node experiments

### `fast-mode-30s`

- branch root: `dea3202`
- worktree: `/tmp/overnight_fast_mode_30s`
- purpose: isolated FAST_MODE line
- allowed content:
  - FAST_MODE infrastructure only
  - approximate node-solve and adaptive activation experiments
  - error-evaluation tooling
- excluded content:
  - any default exact-path semantic change
  - unaccepted exact experiments mixed into default code paths

## File Carry-In Policy

### Exact Line

- initial carry-in from `dea3202`: code only
- immediate additions allowed:
  - reports under `handoff_network_model_20260312/reports`
  - benchmark / profiling scripts that do not alter default exact runtime semantics

### FAST Line

- initial carry-in from `dea3202`: code only
- later selective carry-in source:
  - `fast_mode_snapshot_20260314`
- carry-in rule:
  - only FAST_MODE-isolated infrastructure may be ported
  - any mixed exact experiment must be dropped or rewritten behind FAST-only switches

## Isolation Check

At branch creation time both `exact-baseline-clean` and `fast-mode-30s` point to the same accepted exact baseline commit `dea3202`, so default exact behavior is initially identical on both lines.

## Runtime Data Attachment

The Islam case relies on untracked runtime inputs under `handoff_network_model_20260312/bound/`, which are present in the main worktree but not materialized by `git worktree`.

For both overnight worktrees a read-only symlink was attached:

- `/tmp/overnight_exact_baseline_clean/handoff_network_model_20260312/bound -> /home/xin/River_net_parallel/handoff_network_model_20260312/bound`
- `/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/bound -> /home/xin/River_net_parallel/handoff_network_model_20260312/bound`

The compiled Cython extension was also linked read-only for reproducible runtime parity:

- `cython_cross_section.cpython-311-x86_64-linux-gnu.so`

These attachments do not modify tracked source files and are required for runnable clean worktrees.
