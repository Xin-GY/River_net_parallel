# Overnight Progress Log

## Stage 0

- Recorded current git status and exported worktree/index diffs.
- Verified `main` is clean at `dea3202`.
- Documented the preserved dirty experimental delta from `fast_mode_snapshot_20260314`.
- Created recovery checkpoints:
  - `safety_main_20260314_223414`
  - `fast_mode_snapshot_20260314`
  - `/tmp/fastmode_backup`
- Continue: yes

## Stage 1

- Created isolated exact work line:
  - branch `exact-baseline-clean`
  - worktree `/tmp/overnight_exact_baseline_clean`
- Created isolated FAST work line:
  - branch `fast-mode-30s`
  - worktree `/tmp/overnight_fast_mode_30s`
- Wrote branch layout and carry-in / exclusion policy to keep exact and FAST lines separated.
- Found that `git worktree` does not materialize untracked Islam runtime inputs under `bound/`.
- Attached read-only symlinks for:
  - `bound/`
  - `cython_cross_section.cpython-311-x86_64-linux-gnu.so`
- Verified both worktrees can run the default exact path with a 10-minute smoke:
  - exact line: `181` steps, model time `2.62 s`
  - FAST line baseline: `181` steps, model time `2.55 s`
- Continue: yes
