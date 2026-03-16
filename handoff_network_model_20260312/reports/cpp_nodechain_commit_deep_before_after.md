# Nodechain Commit Deep Before/After

## Candidate

- feature flag:
  - `ISLAM_CPP_USE_NODECHAIN_COMMIT_DEEP=1`
- candidate branch:
  - `feature/cpp-exact-evolve-nodecommit-refresh`

## Exact validation

- 10m strict compare: pass
- 2h strict compare: pass
- 40h strict compare: pass
- 40h compare: `allclose = true`

Compare outputs:

- `reports/cpp_nodecommit_deepcommit_10m_compare.json`
- `reports/cpp_nodecommit_deepcommit_2h_compare.json`
- `reports/cpp_nodecommit_deepcommit_40h_compare.json`

## Evolve/model time

### Branch-local continuation runs

- 10m:
  - accepted replay: `0.667557 s`
  - commit-deep candidate: `0.667691 s`
  - delta: `+0.000134 s`
- 2h:
  - accepted replay: `5.133584 s`
  - commit-deep candidate: `5.103571 s`
  - delta: `-0.030013 s`

### Accepted 40h baseline vs candidate

- accepted baseline: `92.091939 s`
- commit-deep candidate: `91.329929 s`
- delta: `-0.762010 s`
- relative gain: `0.83%`

## 40h nodechain breakdown

- `boundary_updater.total`
  - before: `34.411285 s`
  - after: `33.800367 s`
  - delta: `-0.610918 s`
- `nodechain.total`
  - before: `36.756061 s`
  - after: `35.837393 s`
  - delta: `-0.918668 s`
- `nodechain.apply_and_boundary_closure`
  - before: `14.925780 s`
  - after: `14.675724 s`
  - delta: `-0.250056 s`
- `nodechain.residual_and_ac`
  - before: `0.213633 s`
  - after: `0.211224 s`
  - delta: `-0.002409 s`
- `nodechain.final_apply`
  - before: `2.637463 s`
  - after: `2.457427 s`
  - delta: `-0.180037 s`

## Interpretation

This step improves the intended tail component:

- most of the win is in `final_apply / state commit`
- the rest is small secondary relief from downstream cached reads

It does **not** materially change:

- closure call count
- residual/Ac math
- node iteration structure

That is consistent with the implementation goal: deepen native ownership of nodechain tail state rather than rework the solve itself.
