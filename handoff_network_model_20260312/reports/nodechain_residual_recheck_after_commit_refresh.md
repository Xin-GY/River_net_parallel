# Nodechain Residual Recheck After Commit Refresh

## Question

After the accepted deep-commit checkpoint `9535623`, is residual / Ac / Jacobian / stopping still worth a dedicated deeper native push?

## Evidence

Accepted 40h exact perf:

- `nodechain.total = 35.83739262202289 s`
- `nodechain.apply_and_boundary_closure = 14.67572364397347 s`
- `nodechain.residual_and_ac = 0.21122410095995292 s`
- `nodechain.update_and_stopping = 0.015114254725631326 s`
- `nodechain.final_apply = 2.457426681939978 s`

Accepted 2h exact perf:

- `nodechain.total = 5.20208794681821 s`
- `nodechain.apply_and_boundary_closure = 2.2808734669233672 s`
- `nodechain.residual_and_ac = 0.021312871074769646 s`
- `nodechain.update_and_stopping = 0.0014963731518946588 s`
- `nodechain.final_apply = 0.2225427443627268 s`

## Interpretation

Residual / Ac is no longer a first-order blocker:

- on 40h it is about `0.21 s`
- on 2h it is about `0.02 s`
- even a perfect elimination would not move the branch enough to justify another native push ahead of larger gaps

The largest remaining nodechain-owned costs are still:

1. `apply_and_boundary_closure`
2. `final_apply / state commit`
3. Python-owned refresh tail around closure/commit

## Decision

`residual / Ac / Jacobian / stopping` is a **no-go for now**.

It should only be reconsidered if:

- closure/apply/commit ownership is exhausted, and
- a later profile shows residual-related cost has become a meaningful share again

Current recommendation:

- do not spend the next iteration on residual/Jacobian
- keep focus on larger ownership gaps or branch-level build/layout wins
