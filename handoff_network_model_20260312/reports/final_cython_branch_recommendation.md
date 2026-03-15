# Final Cython Branch Recommendation

## Branch

- branch:
  - `feature/cython-exact-nodechain-top3`
- worktree:
  - `/tmp/feature_cython_exact_nodechain_top3`
- start commit:
  - `dea3202`
- key checkpoints:
  - `4a8bcee` `chore: map node iteration chain for cython exact branch`
  - `425c89e` `chore: add evolve-only serial baseline and hotspot reports`
  - `87bd76d` `feat: add exact cython nodechain and roe kernels (+2.63x 40h evolve)`

## Current Status

### Nodechain Cython Exact

- implemented:
  - yes
- validated:
  - yes on 10-minute and 2-hour cases

### Serial Top 3 Coverage

- internal node iteration chain:
  - Cython exact implemented
- `Caculate_Roe_Flux_2`:
  - Cython exact implemented for the general-HR batch loop
- `Update_cell_proprity2`:
  - Cython kernel implemented, but not yet accepted for the exact candidate due to drift

## Best Exact Candidate So Far

- flags:
  - `ISLAM_USE_CYTHON_NODECHAIN=1`
  - `ISLAM_USE_CYTHON_ROE_FLUX=1`
  - `ISLAM_USE_CYTHON_UPDATE_CELL=0`
- status:
  - exact on 10-minute, 2-hour, and 40-hour cases
  - 40-hour evolve/model time: `213.933772 s`
  - 40-hour evolve wall time: `217.559511 s`
  - 40-hour evolve/model speedup vs serial Python baseline: `2.628x`
  - 40-hour evolve wall speedup vs serial Python baseline: `2.597x`

## Current Recommendation

- candidate new baseline:
  - yes, for the `nodechain + Roe flux` pair
- recommended default composition for the next optimization baseline:
  - enable the exact nodechain kernel
  - enable the exact Roe-flux kernel
  - keep the update-cell kernel disabled by default

## Reasoning

- this branch already shows a large single-process evolve-only gain on 10-minute and 2-hour cases
- the large gain comes mainly from the Roe-flux outer-loop Cythonization
- nodechain Cythonization is exact and stable, and helps remove Python orchestration overhead
- the update-cell kernel is promising, but still needs numerical debugging

## Why This Recommendation Holds

- the branch has now met the branch goal:
  - internal-node chain Cythonized
  - Top 3 serial hotspot set covered
  - best exact candidate materially faster than single-process Python baseline
  - no numerical drift in the accepted candidate
- the remaining non-accepted kernel is isolated behind its own flag:
  - `ISLAM_USE_CYTHON_UPDATE_CELL`

## Historical Side Evidence

For context only, the repository's previously documented fastest CPU path was a process-based route, not a single-process route:

- source:
  - `docs/CURRENT_STATUS.md`
- historical 40-hour model time:
  - `139.86 s`
- historical 40-hour wall:
  - `147.10 s`

This Cython branch does not beat that historical multi-process number, but it was not designed to. Its value is that it reduces the single-process exact baseline from `562.26 s` to `213.93 s` without changing results, which makes it a much stronger base for any later optimization work.
