# C++ Kernelize-Next Serial Exact Baseline

## Scope

- branch: `feature/cpp-exact-evolve-kernelize-next`
- base checkpoint: `835cf1f`
- execution mode:
  - `ISLAM_USE_PARALLEL=0`
  - `ISLAM_FAST_MODE=0`
  - `ISLAM_USE_CPP_EVOLVE=1`
  - `ISLAM_CPP_THREADS=0`
  - `ISLAM_USE_CYTHON_NODECHAIN=1`
  - `ISLAM_USE_CYTHON_ROE_FLUX=1`
  - `ISLAM_CPP_USE_UPDATE_CELL=0`
- timing rule:
  - headline numbers only count `evolve/model time`
  - initialization, Fine interpolation, section-table build, and prepare-time marshaling are excluded

## Corrected Baseline Runs

These runs were produced after rebuilding `cython_cross_section` in this worktree. Only these runs are valid for the current branch baseline.

| Case | Summary JSON | Steps | Evolve/model time (s) | Evolve wall (s) |
| --- | --- | ---: | ---: | ---: |
| 10m | `cpp_kernelize_next_10m_after_crosssection_summary.json` | 181 | 1.459050 | 1.487436 |
| 2h | `cpp_kernelize_next_2h_after_crosssection_summary.json` | 1482 | 12.330136 | 12.534430 |
| 40h | `cpp_kernelize_next_40h_after_crosssection_summary.json` | 29783 | 206.306033 | 210.424964 |

## Invalid / Discarded Runs

The following early runs were taken before the local `cython_cross_section` extension was rebuilt in this worktree. They are not representative and must not be used for hotspot ranking or branch-level benchmark claims.

- `cpp_kernelize_next_10m_summary.json`
- `cpp_kernelize_next_2h_summary.json`
- `cpp_kernelize_next_2h_noperf_summary.json`
- `cpp_kernelize_next_2h_noperf_solo_summary.json`
- `cpp_kernelize_next_2h_cprofile_summary.json`
- `cpp_kernelize_next_2h_perf.json`
- `cpp_kernelize_next_40h_noperf_summary.json`

Root cause:

- this worktree initially did not have the compiled `cython_cross_section` extension in place
- the runtime silently fell back to a much slower path
- once `build_cython_cross_section.py build_ext --inplace` was rerun, timings returned to the expected range

## Current Baseline Interpretation

- the current branch is still effectively the `835cf1f` bridge line plus safe reporting/profiling support
- 40h evolve time on this branch is `206.306033 s`
- the earlier source-branch bridge checkpoint recorded `205.593739 s`
- the delta is small enough that it should be treated as baseline noise rather than a real regression until deeper kernel changes land

## Implication For Next Stage

The bridge is already active, but this baseline confirms that the main remaining cost is still inside:

1. internal-node exact orchestration and boundary closure
2. river-step numeric kernels
3. Python/Cython/C++ step crossings

The next accepted gains therefore have to come from deeper native kernelization, not from bridge setup alone.
