# FAST_MODE Adaptive Design

## Goal

Keep the default exact path untouched while making `FAST_MODE` more selective on long runs. The first adaptive version does not change river-body kernels or default exact numerics; it only decides when the approximate internal-node solver may be used.

## Why Adaptive Instead of Global Fixed FAST

The previous fixed-parameter `FAST_MODE` variants improved short runs, but on the 40-hour full case they showed two problems:

- speedup was still far from the `30 s` wall-clock target
- control-point `Q` error could exceed the intended `1e-2` ceiling

Stage-3 dt profiling already showed that the dominant limiter is concentrated around a small set of internal-node-adjacent branch ends. That makes selective activation more promising than enabling the fast node solver on every step.

## Activation Signals

Current adaptive gating only applies when all of the following are true:

1. `FAST_MODE` is enabled.
2. The selected fast node solver is an internal-node response solver (`response_root` or `response_corrector`).
3. The current global dt limiter is classified as `internal_node`.
4. The limiter node is one of the network internal nodes.
5. The same limiter node has repeated for at least `fast_adaptive_min_streak` consecutive steps.
6. The previous converged node level change stays below `fast_adaptive_max_level_delta`.
7. The previous residual stays below `fast_node_q_tol * fast_adaptive_residual_factor`.
8. The limiter is not tagged as dry / near-dry when `fast_adaptive_disable_near_dry=1`.

If any check fails, the run falls back to the existing exact internal-node solve for that step.

## New FAST_MODE Controls

- `ISLAM_FAST_ADAPTIVE`
- `ISLAM_FAST_ADAPTIVE_REQUIRE_INTERNAL_LIMITER`
- `ISLAM_FAST_ADAPTIVE_DISABLE_NEAR_DRY`
- `ISLAM_FAST_ADAPTIVE_MIN_STREAK`
- `ISLAM_FAST_ADAPTIVE_LEVEL_DELTA`
- `ISLAM_FAST_ADAPTIVE_RESIDUAL_FACTOR`

These switches only affect the FAST line. Default exact behavior is unchanged when `ISLAM_FAST_MODE=0`.

## Non-Goals

This adaptive pass intentionally does **not**:

- change the default exact path
- change stage-boundary fast-path admission
- introduce response-table defaulting into exact mode
- reduce river-body time steps by changing exact CFL logic
- reuse rejected exact-only orchestration experiments

## Expected Failure Modes

- If the 40-hour limiter moves between nodes too often, the streak gate may keep FAST mostly disabled.
- If the limiter spends long periods in near-dry states, the near-dry guard may also keep FAST disabled.
- If the river-body kernels dominate total cost, adaptive node solve alone cannot get close to `30 s`.

## Overnight Outcome

The adaptive gate was not the winning path for the 40-hour target.

- `adaptive_cfl125` improved on the earliest FAST baseline, but it still stayed at `193.09 s` wall time.
- Full 40-hour sweeps showed that fixed aggressive FAST with periodic internal-node refresh dominates the adaptive gate on the current case.
- The useful new control was not "whether FAST is enabled", but "how often internal nodes are fully refreshed".

## Structural FAST Replacement

The current best-performing FAST family adds two new controls, still isolated from default exact mode:

- `ISLAM_FAST_NODE_REFRESH_EVERY`
- `ISLAM_FAST_NODE_REFRESH_MODE=hold|predict`

Current conclusion:

- `predict` between refreshes is too unstable on this case and quickly becomes unusable.
- `hold` between refreshes is much more stable.
- `refresh_every=3` is a strong speed/accuracy tradeoff point.
- More aggressive CFL growth can push wall-clock toward `60 s`, but with rapidly growing `Q` error.
