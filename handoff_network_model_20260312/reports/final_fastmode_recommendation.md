# Final FAST_MODE Recommendation

## Executive Summary

The overnight FAST-only work did not reach the `30 s` target, but it materially improved the 40-hour full case.

- fastest candidate so far:
  - `response_root_iter2_cfl30_dt20_fixed_refresh3hold`
  - wall `59.379443 s`
  - model/evolve `56.126713275909424 s`
  - steps `9836`
  - max_abs overall `0.5854339599609375`
- best balanced candidate so far:
  - `response_root_iter2_cfl20_dt135_fixed_refresh3hold`
  - wall `87.270943 s`
  - model/evolve `83.9566490650177 s`
  - steps `14758`
  - max_abs overall `0.07947444915771484`

Relative to the accepted exact baseline used in this FAST line (`wall 147.10 s`, `model 139.86 s`):

- best balanced candidate:
  - wall speedup `1.6856x`
  - model speedup `1.6659x`
- speed-optimal candidate:
  - wall speedup `2.4773x`
  - model speedup `2.4919x`

## What Actually Worked

The highest-value FAST change was not the earlier adaptive gate. The useful change was:

1. aggressive fixed FAST node solve
2. periodic internal-node refresh
3. `hold` between refreshes, not `predict`

The `predict` refresh path was consistently too unstable on the 40-hour case. The `hold` path gave the best speed/robustness tradeoff.

## Current Best Candidates

### Best Balanced

- label: `response_root_iter2_cfl20_dt135_fixed_refresh3hold`
- wall: `87.270943 s`
- model/evolve: `83.9566490650177 s`
- total steps: `14758`
- mean dt: `9.757419704567015 s`
- mean NSE delta: `-0.001115237434205496`
- max abs overall: `0.07947444915771484`
- max peak error overall: `0.017249107360839844`
- max arrival time error: `0.0 h`
- volume error: `-1.2469776837742657e-06`

Detailed report:

- [fast_eval_vs_accepted40h.md](/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/reports/fast_eval_vs_accepted40h.md)

### Fastest

- label: `response_root_iter2_cfl30_dt20_fixed_refresh3hold`
- wall: `59.379443 s`
- model/evolve: `56.126713275909424 s`
- total steps: `9836`
- mean dt: `14.640097600650671 s`
- mean NSE delta: `-0.020884883378968933`
- max abs overall: `0.5854339599609375`
- max peak error overall: `0.01532745361328125`
- max arrival time error: `0.0 h`
- volume error: `-1.2295487328292198e-06`

Detailed report:

- [fast_eval_speed_opt_vs_accepted40h.md](/tmp/overnight_fast_mode_30s/handoff_network_model_20260312/reports/fast_eval_speed_opt_vs_accepted40h.md)

## Distance To 30 Seconds

The current closest result is `59.379443 s`, still `29.379443 s` above the `30 s` goal.

This is no longer just a tiny tuning gap.

## Why 30 Seconds Is Still Hard

The updated speed-optimal dt profile shows:

- total steps: `9836`
- mean dt: `14.64 s`
- limiter category share: `100% internal_node`
- dominant limiter location: `river1 / cell15 / n8`
- model time per step: about `5.855e-3 s`

Implication:

At the current fastest configuration, reaching `30 s` would require roughly one of these:

- keep `9836` steps but cut per-step model cost by about another `46%`
- keep the current per-step cost but reduce steps from `9836` to roughly `5100`
- or achieve both together

So the remaining gap is now mixed:

- still strongly a **step-count** problem
- but no longer only a step-count problem
- once steps are near `1e4`, **single-step cost** also matters

## What Is No Longer Worth Chasing

- adaptive gate alone
  - it is dominated by fixed aggressive FAST plus periodic refresh
- `predict` refresh
  - too unstable on the 40-hour case
- exact-only cleanup for this objective
  - useful for hygiene, but not for the `30 s` FAST target
- tiny IPC-only tweaks
  - not enough leverage for the current goal

## Next Three Recommended Directions

1. FAST-only asynchronous or sparse node coupling
   - do not just "refresh every k steps"
   - instead refresh only the limiter-driving nodes, and leave the rest on held/predicted levels

2. FAST-only multi-rate stepping around internal-node hot spots
   - current limiter is still internal-node dominated
   - splitting hotspot node neighborhoods from the rest of the network is the most plausible way to cut total steps further

3. FAST-only local river kernel acceleration
   - after the structural step-count gain already achieved, the fastest path now also needs lower per-step cost
   - priority functions remain the local river evolve kernels, not exact orchestration cleanup
