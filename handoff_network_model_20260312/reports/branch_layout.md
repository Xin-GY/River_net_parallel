# Branch Layout

- Branch: `feature/cython-exact-nodechain-top3`
- Start commit: `dea3202` (`perf: isolate runtime sections and speed general HR path (+5.2% evolve, +4.9% wall)`)
- Main repository worktree kept on: `/home/xin/River_net_parallel` (`main`)
- Isolated Cython worktree: `/tmp/feature_cython_exact_nodechain_top3`
- Benchmark policy on this branch:
  - `ISLAM_USE_PARALLEL=0`
  - `ISLAM_FAST_MODE=0`
  - no process/thread pool benchmarks
  - headline numbers must exclude initialization and focus on `Evolve`

## Included Baseline Content

- Clean exact baseline code from `dea3202`
- Existing single-process Python implementation
- Existing Cython hydraulic table module:
  - `cython_cross_section.pyx`
  - `build_cython_cross_section.py`
- Existing serial and parallel code paths remain in the tree for compatibility, but only the serial path is benchmarked on this branch

## Explicitly Excluded Experimental Content

- FAST refresh / adaptive refresh logic from `fast-mode-30s`
- FAST sweep harnesses and candidate ranking logic
- FAST-only error reports and matrix reports
- response-table and predictor experiments
- pool-specific benchmark conclusions as gating evidence for this branch
- any unaccepted exact orchestration experiments from earlier overnight work

## Preservation Status Of Prior Experimental Line

- FAST experimental branch preserved separately:
  - branch: `fast-mode-30s`
  - latest preservation checkpoint: `77c714e`
- additional preservation branch:
  - `backup/pre-cython-branch-20260315-224054`
- untracked FAST artifacts snapshot:
  - `/tmp/pre_cython_branch_20260315-224054_untracked_snapshot.tar.gz`

## Files Intentionally Brought Forward Only As References

- `Rivernet.py`
- `river_for_net.py`
- `parallel_river_pool.py`
- `Islam.py`
- `cython_cross_section.pyx`
- `build_cython_cross_section.py`
- `config.py`

These are used to map the serial node-iteration chain and identify which serial kernels should be moved into exact Cython entry points.
