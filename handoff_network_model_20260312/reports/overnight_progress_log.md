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

## Stage 2

- Added safe benchmark infrastructure:
  - `tools/overnight_benchmark.py`
  - env-gated `ISLAM_SAVE_RUN_SUMMARY=1`
  - network-level `run_summary.json` export in `Rivernet.py`
- Fixed report-root isolation so benchmark reports stay in the exact worktree, not `main`.
- Ran fresh exact benchmarks from the clean exact line:
  - `exact_10m`: strict compare passed, `allclose=true`
  - `exact_40h`: strict compare passed, `allclose=true`
- Re-evaluated current FAST 40h artifacts against the fresh exact-40h reference:
  - `fast_40h_iter5_cfl125`
  - `fast_40h_iter5_nocfl`
- Wrote unified matrix:
  - `reports/benchmark_matrix.md`
- Key finding:
  - current clean exact rerun is still slower than the accepted 40h reference, so no exact performance commit is acceptable yet
  - current FAST artifacts are faster than the clean exact rerun, but still far from `30 s` and still exceed the desired max-abs threshold on `Q`
- Continue: yes
