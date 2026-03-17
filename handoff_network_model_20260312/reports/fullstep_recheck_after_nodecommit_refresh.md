# Fullstep Recheck After Nodecommit Refresh

## Question

After the accepted deep-commit checkpoint `9535623`, is it time to resume a fullstep native-loop effort?

## Evidence

Accepted 40h exact perf:

- `bridge.python_crossings = 297830`
- `boundary_updater.total = 33.8003668001038 s`
- `nodechain.total = 35.83739262202289 s`
- `river_step.flux = 39.82027102151187 s`
- `river_step.assemble = 5.721883070305921 s`
- `river_step.update_cell = 2.5711693117627874 s`

Known historical result on this branch family:

- direct-dispatch / fullstep-shape experiment improved short runs
- but regressed 40h exact full case

## Interpretation

Crossing cost is real, but it is not yet the safest next lever.

Reasons:

- the largest remaining 40h costs are still native numerical domains:
  - Roe flux
  - nodechain apply/closure
  - assemble/update tails
- the previous fullstep-like dispatch reshape already showed the core risk:
  - short cases got better
  - 40h exact full case got worse
- current evidence still favors ownership pushdown over another loop-shape experiment

## Decision

`fullstep native loop` is a **no-go for now**.

Revisit only if:

- nodechain tail and flux ownership stop moving materially, and
- a new profile shows boundary crossing / marshaling is once again the dominant remaining blocker on 40h

Current recommendation:

- do not re-open fullstep loop work in the immediate next iteration
- stay with the accepted `9535623` path and look for higher-confidence exact gains
