# C++ Nodechain Refresh Deep Implementation Notes

## Experiment preservation

The rejected stage-3 experiment is preserved in the source worktree at:

- `/tmp/feature_cpp_exact_evolve_nodecommit_refresh`

Tracked-source diff snapshot:

- [cpp_nodechain_refresh_deep_experiment.diff](/tmp/feature_cpp_exact_evolve_nodecommit_refresh/handoff_network_model_20260312/reports/cpp_nodechain_refresh_deep_experiment.diff)

This continuation branch starts from the last accepted checkpoint:

- `9535623` `perf: deepen exact nodechain commit ownership (+0.8% 40h evolve)`

## Candidate A: Cython-native refresh

### What changed

- added `ISLAM_CPP_USE_NODECHAIN_REFRESH_DEEP`
- wired the flag in:
  - `Islam.py`
  - `Rivernet.py`
  - `tools/profile_cpp_exact_serial.py`
- moved refresh work into `cython_node_iteration.pyx`

### Outcome

- fast on 10m
- not exact

Observed symptom:

- CFL history drifted early
- step timing diverged
- result compare failed on 10m

Root cause summary:

- the inline refresh path changed accepted state-update ordering inside the nodechain tail
- that ordering difference fed back into CFL / global dt scheduling

Conclusion:

- rejected
- do not continue from this implementation

## Candidate B: Single-cell C++ exact refresh kernel

### What changed

- switched `cython_node_iteration` build mode to C++
- added `update_single_cell_properties_exact(...)` in:
  - `cpp/river_kernels.hpp`
  - `cpp/river_kernels.cpp`
- invoked that single-cell C++ kernel from `cython_node_iteration.pyx`
- preserved exact formulas and ordering closely enough to restore strict compare

### Outcome

- exact on 10m and 2h
- slower than the accepted `9535623` baseline

Important side effect:

- compiling `cython_node_iteration` as C++ in this shape increased overhead even when the refresh-deep flag was not the dominant algorithmic change
- accepted-path 10m timing after the build-shape change rose materially, which makes this implementation unattractive even before 40h

Conclusion:

- exact but negative value
- rejected as an accepted path

## Decision

Stage 3 is a no-go in its current forms:

- Candidate A:
  - good speed potential
  - fails exactness
- Candidate B:
  - exact
  - slower than accepted baseline

The accepted path remains:

- commit deep accepted at `9535623`
- refresh deep disabled

Next work should not continue from either rejected stage-3 variant.
