# Final Overnight Recommendation

## Bottom Line

The overnight evidence points more strongly to **total step count / dt-limiter structure** than to small per-step Python overhead as the primary barrier to a `30 s` wall-clock target.

## Why This Is The Current Conclusion

1. Exact and FAST 40-hour runs are both overwhelmingly limited by internal-node-adjacent CFL events.
2. The best adaptive FAST candidate reduced steps from `29969` to `23895`, but wall-clock still stayed at `193.09 s`.
3. That best adaptive run is still `163.09 s` away from the `30 s` target.
4. At `23895` steps, hitting `30 s` would require roughly `0.001255 s/step`, while the current adaptive FAST run still spends about `0.007815 s/step`, a further `6.22x` reduction.
5. Exact-only local-kernel cleanup improved the clean rerun modestly, but not nearly enough to close the gap to the accepted exact baseline, let alone `30 s`.

## Exact Line Recommendation

The next exact round should only pursue changes that preserve strict equality and target river-body kernels directly:

1. `Caculate_Roe_Flux_2`
2. `Assemble_Flux_2`
3. `Update_cell_proprity2`

These are still the best candidates for deeper Cython batch-kernel work. The work should remain isolated from node-solve experimentation.

## FAST Line Recommendation

The best current FAST candidate is:

- branch/worktree: `fast-mode-30s` at `/tmp/overnight_fast_mode_30s`
- result: `result/exp_fastmode_adaptive_cfl125_py311_40h`
- wall: `193.09 s`
- model/evolve: `186.73348426818848 s`
- control-point max abs: `0.031519703004168065`

This is a modest improvement over the previous FAST best, but it is still far from the `30 s` target and still above the desired `1e-2` max-abs ceiling.

## Next-Level Options Ranked By Likely Return

1. Local time stepping / multi-rate stepping
   - Highest leverage against the step-count wall.
   - Most invasive numerically and architecturally.
2. Semi-implicit / implicit internal-node coupling
   - Directly targets the recurring internal-node CFL bottleneck.
   - More mathematically invasive than the current explicit architecture.
3. Deeper kernelization beyond current Python/Cython split
   - Push larger river-body loops into Cython/C++/Rust.
   - Helps per-step cost, but by itself is unlikely to deliver `30 s` without step-count relief.

## Recommendation To Carry Forward

Treat the accepted exact baseline as stable. Keep the new FAST adaptive path isolated as an experimental speed/accuracy tradeoff. If the real target remains `30 s`, the next round should assume that architecture-level step-count reduction is required.
