## Configuration

Before:

- accepted phase-3 exact path
- `ISLAM_CPP_USE_ROE_FLUX_DEEP=0`

After:

- same accepted exact path
- `ISLAM_CPP_USE_ROE_FLUX_DEEP=1`

## Exact compare

Strict compare vs accepted phase-3 baseline:

- 10m: pass
- 2h: pass
- 40h: pass

Artifacts:

- `reports/cpp_fluxdeep_10m_compare.json`
- `reports/cpp_fluxdeep_2h_compare.json`
- `reports/cpp_fluxdeep_40h_compare.json`

## Evolve/model time

- 10m: `0.860548 s -> 0.843206 s`
- 2h: `6.488843 s -> 6.374767 s`
- 40h: `109.425894 s -> 106.473473 s`

40h net gain:

- `-2.952421 s`
- about `+2.70%`

## Stage-level 40h before/after

- `river_dispatch.Caculate_Roe_Flux_2.time`
  - `42.943128 s -> 40.093720 s`
  - delta `-2.849408 s`
- `boundary_updater.total`
  - `48.312066 s -> 48.633332 s`
  - delta `+0.321266 s`
- `nodechain.total`
  - `64.568132 s -> 65.117052 s`
  - delta `+0.548920 s`

Interpretation:

- The gain is real and local to Roe flux ownership.
- This is not another short-case-only improvement:
  - 10m improved
  - 2h improved
  - 40h improved
- The next limiting block is no longer Roe flux alone; nodechain closure/body still dominates the remaining 40h cost.
