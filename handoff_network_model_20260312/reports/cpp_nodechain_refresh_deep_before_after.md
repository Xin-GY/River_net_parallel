# C++ Nodechain Refresh Deep Before/After

## Baseline

Accepted checkpoint:

- `9535623` `perf: deepen exact nodechain commit ownership (+0.8% 40h evolve)`

Accepted exact configuration:

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_NODECHAIN_PREBOUND_FAST=1`
- `ISLAM_CPP_USE_NODECHAIN_DEEP_APPLY=1`
- `ISLAM_CPP_USE_NODECHAIN_COMMIT_DEEP=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_ROE_FLUX_DEEP=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_CPP_USE_ASSEMBLE=1`
- `ISLAM_CPP_USE_ROE_MATRIX=1`
- `ISLAM_CPP_USE_FACE_UC=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

Baseline timings:

- 10m: `0.6676914691925049 s`
- 2h: `5.10357141494751 s`
- 40h: `91.32992911338806 s`

## Candidate A: inline Cython refresh

Files:

- perf: `cpp_nodecommit_refreshdeep_10m_perf.json`
- compare: `cpp_nodecommit_refreshdeep_10m_compare.json`

Result:

- 10m model time: `0.47945213317871094 s`
- speed vs accepted 10m: faster
- exact compare: failed

Failure signature:

- `cfl_history.csv` drift
- `time` max abs: `0.4793701171875`
- `global_dt` max abs: `0.5033385753631592`

Interpretation:

- this path is fast but not exact
- rejected immediately

## Candidate B: single-cell C++ exact refresh

Files:

- 10m perf: `cpp_nodecommit_refreshdeep_cpp_10m_perf.json`
- 10m compare: `cpp_nodecommit_refreshdeep_cpp_10m_compare.json`
- 2h perf: `cpp_nodecommit_refreshdeep_cpp_2h_perf.json`
- 2h compare: `cpp_nodecommit_refreshdeep_cpp_2h_compare.json`

Results:

- 10m model time:
  - accepted: `0.6676914691925049 s`
  - candidate: `1.0589027404785156 s`
  - delta: `+58.6%` slower
- 2h model time:
  - accepted: `5.10357141494751 s`
  - candidate: `8.042586088180542 s`
  - delta: `+57.6%` slower
- 10m strict compare: pass
- 2h strict compare: pass

Additional isolation check:

- accepted configuration rebuilt through the C++-compiled `cython_node_iteration` shape:
  - 10m model time: `1.091275930404663 s`

Interpretation:

- the conservative exact refresh kernel restores correctness
- but the surrounding build/ownership shape is materially slower
- this is not worth extending to 40h as an accepted candidate

## Decision

Stage-3 `_refresh_cell_state` deeper ownership is currently rejected:

- inline Cython refresh:
  - faster
  - not exact
- single-cell C++ exact refresh:
  - exact
  - substantially slower

Accepted recommendation:

- keep `ISLAM_CPP_USE_NODECHAIN_REFRESH_DEEP=0`
- continue from `9535623`
- prioritize only the next work that can plausibly beat the accepted 40h result on full case
