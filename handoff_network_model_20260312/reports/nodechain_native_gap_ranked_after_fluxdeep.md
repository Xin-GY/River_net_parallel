## Ranking basis

Accepted exact profile sources:

- current-branch 2h profile:
  - `reports/cpp_nodechainpush_accepted_2h_perf.json`
- accepted 40h reference from prior branch at identical code state:
  - `nodechain.total = 65.117052 s`
  - `nodechain.apply_and_boundary_closure = 25.879760 s`
  - `nodechain.residual_and_ac = 1.742821 s`
  - `nodechain.final_apply = 4.360243 s`

## Ranked remaining native gaps

1. `apply_and_boundary_closure` deeper ownership
   - strongest expected 40h payoff
   - reason:
     - largest named nodechain sub-block
     - still executes through Python river closure/commit helpers per branch
     - contains repeated closure context use and repeated ghost-state refresh

2. final apply / state commit deeper ownership
   - second expected payoff
   - reason:
     - repeats the same Python-owned closure/commit path after convergence
     - cheaper than main apply block, but structurally identical and likely unlocks later full native nodechain ownership

3. residual / `Ac` native body
   - third expected payoff
   - reason:
     - smaller named block than apply/final apply
     - but still holds repeated width lookup and object access overhead
     - should benefit after apply-side data ownership is made native

4. final cache/write-back cleanup
   - low-to-medium payoff
   - mostly bookkeeping after the larger blocks above

5. stopping / update scalar logic
   - low payoff
   - already mostly in compiled Cython scalar loops

## Recommended order

1. `apply_and_boundary_closure` deeper native ownership
2. final apply / state commit native ownership
3. residual / `Ac` / stopping body nativeization

This order differs slightly from a pure function-name reading because the accepted path shows that:

- apply and final apply are still paying the same Python closure/commit tax
- residual/`Ac` is real, but smaller in absolute time

So the first real step should be to remove the per-closure Python helper path, not to micro-optimize the smaller residual block first.
