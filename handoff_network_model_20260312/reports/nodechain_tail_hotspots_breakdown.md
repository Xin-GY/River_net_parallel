# nodechain tail hotspots breakdown

## measurement basis

This breakdown uses:

- branch-local accepted 2h replay:
  - `reports/cpp_nodecommit_accepted_2h_perf.json`
  - `reports/cpp_nodecommit_accepted_2h_cprofile.prof`
- accepted 40h reference from the identical source commit:
  - `feature/cpp-exact-evolve-nodechain-deepnative`
  - 40h `evolve/model = 92.091939 s`
  - `reports/cpp_nodechain_deepapply_40h_perf.json`

The new worktree replay was exact-compared back to the source accepted outputs:

- `cpp_nodecommit_accepted_10m_compare.json`: `allclose = true`
- `cpp_nodecommit_accepted_2h_compare.json`: `allclose = true`

## direct nodechain timers

### 2h accepted replay

- `nodechain.total = 2.923550 s`
- `nodechain.apply_and_boundary_closure = 1.278234 s`
- `nodechain.residual_and_ac = 0.018511 s`
- `nodechain.update_and_stopping = 0.001284 s`
- `nodechain.final_apply = 0.129647 s`
- `nodechain.boundary_closure_calls = 336020`
- `nodechain.deep_apply_hits = 336020`
- `nodechain.cython_to_python_boundary_calls = 0`
- `nodechain.cython_to_python_width_calls = 0`

### 40h accepted reference

- `nodechain.total = 36.756061 s`
- `nodechain.apply_and_boundary_closure = 14.925780 s`
- `nodechain.residual_and_ac = 0.213633 s`
- `nodechain.update_and_stopping = 0.016801 s`
- `nodechain.final_apply = 2.637463 s`
- `nodechain.boundary_closure_calls = 4010220`

## cProfile support for tail ownership

From branch-local 2h cProfile:

- `river_for_net._refresh_cell_state`: `347876` calls, `2.287927 s` cumulative
- `Rivernet.Update_internal_boundary_conditions`: `2.619 s` cumulative
- `Rivernet._try_update_internal_boundary_conditions_cython`: `2.613 s` cumulative

Interpretation:

- `_refresh_cell_state` is now the biggest remaining Python-owned cost near the nodechain tail
- deep-apply path executes once per successful closure, so most of those refresh calls are nodechain-owned rather than river-step-owned

## top 5 nodechain tail hotspots

### 1. `_refresh_cell_state` after successful closure

- primary cost type:
  - Python object/method overhead
  - repeated state refresh work
  - repeated per-call geometry/state scatter
- evidence:
  - `347876` cumulative calls in 2h cProfile
  - nodechain deep apply hits exactly track closure count

### 2. `apply_and_boundary_closure`

- 2h: `1.278234 s`
- 40h: `14.925780 s`
- primary cost type:
  - numerical loop plus remaining Python-owned refresh tail

### 3. `final_apply`

- 2h: `0.129647 s`
- 40h: `2.637463 s`
- primary cost type:
  - final closure replay
  - Python boundary-face attr sync
  - commit/write-back tail

### 4. Python boundary-face state scatter

- not timed as its own counter yet
- currently included inside `final_apply`
- primary cost type:
  - Python attribute writes
  - repeated per-branch state scatter

### 5. residual / Ac

- 2h: `0.018511 s`
- 40h: `0.213633 s`
- primary cost type:
  - numerical loop
- conclusion:
  - no longer the first place to spend effort

## takeaway

The tail is no longer dominated by residual/Jacobian math. It is dominated by:

1. Python-owned exact refresh after closure
2. final apply / commit / write-back ownership
3. only then residual/Jacobian if the first two stop moving
