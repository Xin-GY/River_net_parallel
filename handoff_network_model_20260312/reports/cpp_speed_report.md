# C++ Evolve Bridge Speed Report

## Scope

- branch: `feature/cpp-exact-evolve-fullchain`
- timing policy: `evolve/model time` only
- initialization, Fine, section-table construction, coordinate conversion, and final write-out are excluded from the headline timing
- comparison target in this report:
  - single-process `cython exact serial`
  - single-process `cpp bridge + explicit cython nodechain/roe kernels`

## Runtime Flags

- exact serial baseline:
  - `ISLAM_USE_CPP_EVOLVE=0`
  - `ISLAM_USE_CYTHON_NODECHAIN=1`
  - `ISLAM_USE_CYTHON_ROE_FLUX=1`
  - `ISLAM_USE_CYTHON_UPDATE_CELL=0`
- cpp bridge candidate:
  - `ISLAM_USE_CPP_EVOLVE=1`
  - `ISLAM_CPP_THREADS=0`
  - `ISLAM_USE_CYTHON_NODECHAIN=1`
  - `ISLAM_USE_CYTHON_ROE_FLUX=1`
  - `ISLAM_USE_CYTHON_UPDATE_CELL=0`

## 10-Minute Case

- `cython exact serial`
  - model/evolve: `1.471941 s`
  - wall: `1.501918 s`
  - steps: `181`
- `cpp bridge`
  - model/evolve: `1.466367 s`
  - wall: `1.494968 s`
  - steps: `181`
- delta vs exact serial:
  - model/evolve: `-0.005574 s`
  - wall: `-0.006950 s`

## 2-Hour Case

- `cython exact serial`
  - model/evolve: `11.697025 s`
  - wall: `11.899289 s`
  - steps: `1482`
- `cpp bridge`
  - model/evolve: `11.385013 s`
  - wall: `11.582971 s`
  - steps: `1482`
- delta vs exact serial:
  - model/evolve: `-0.312012 s`
  - wall: `-0.316318 s`

## 40-Hour Full Case

- `cython exact serial`
  - model/evolve: `206.436461 s`
  - wall: `210.395574 s`
  - steps: `29783`
- `cpp bridge`
  - model/evolve: `205.593739 s`
  - wall: `209.546805 s`
  - steps: `29783`
- delta vs exact serial:
  - model/evolve: `-0.842722 s`
  - wall: `-0.848769 s`

## Interpretation

- The current `cpp bridge` is not yet the full C++ numerical core; it is an exact compiled orchestrator plus C++ output buffer that reuses the validated cython exact kernels already present on this branch.
- Even at this partial stage, the bridge is not neutral: it shows a small but repeatable evolve-time win on 10-minute, 2-hour, and 40-hour cases.
- The next meaningful step is no longer “prove the bridge can run”; that is now done.
- The next meaningful step is to migrate actual river-step kernels and node-coupling compute from Python/Cython orchestration into C++ runtime kernels, then re-measure against this checkpoint.
