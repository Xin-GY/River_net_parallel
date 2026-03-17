# Overnight Progress Log

## Phase 0

- Created a clean continuation branch from accepted checkpoint `9a7c094`.
- Added a fresh worktree at `/tmp/feature_cpp_exact_accepted_reaudit_after_rectflux`.
- Recorded preflight git status and a concrete exclusion list for generated
  artifacts and benchmark outputs.
- Confirmed this round will benchmark only the accepted exact path, from the
  worktree root, without carrying rejected refresh/fullstep/build-flag
  variants.

## Next

- Rebuild local extensions in the new worktree.
- Re-run 10m / 2h / 40h accepted exact profiles.
- Produce a fresh hotspot audit before choosing a single next blocker.

## Phase 1

- Replayed the accepted exact path in the clean continuation worktree for 10m, 2h,
  and 40h from the worktree root.
- Verified exact reproduction against the accepted `rectdeep` outputs from the source
  worktree for all three cases.
- Fresh replay numbers:
  - 10m: `0.9353327751159668 s`
  - 2h: `6.821141719818115 s`
  - 40h: `63.882303953170776 s`
- Re-audited the accepted path instead of inheriting older hotspot assumptions.

## Phase 2

- Re-ranked the current first-order blockers using the fresh 40h perf JSON plus the 2h
  cProfile drilldown.
- Chose exactly one next move:
  - deeper exact ownership for the external boundary update chain
- Explicitly rejected repeating old no-go directions:
  - refresh deep
  - residual/Jacobian deep
  - fullstep loop
  - build-flag experimentation
  - dispatch reshaping

## Next

- Implement the external boundary exact ownership push behind a feature flag.
- Validate 10m / 2h / 40h strict compare before considering it as a new accepted exact candidate.

## Phase 3

- Implemented the external-boundary deep path behind feature flags.
- First 40h rerun failed for a tooling reason, not a physics reason:
  - this worktree had not rebuilt `cython_cpp_bridge`
  - `ISLAM_USE_CPP_EVOLVE=1` therefore fell back to Python `_evolve_base`
- Rebuilt `build_cpp_exact_kernels.py`, verified `cpp_run_network_evolve_serial`
  is available again, and reran all validation from the accepted exact path.
- Full external deep:
  - 10m strict compare: pass
  - 2h strict compare: pass
  - 40h model time: `54.386069536209106 s`
  - 40h strict compare: fail
- Inflow-only external deep:
  - 10m strict compare: pass
  - 2h strict compare: pass
  - 40h model time: `54.4336314201355 s`
  - 40h strict compare: fail
- Both variants diverge first at the same point:
  - `cfl_history.csv` row `3944`
  - time `19749.31640625 s`
  - field `river13`
  - delta `4.76837158203125e-07`
- Rechecked native interpolation itself against the Python lambda path over all
  accepted 40h boundary times:
  - max absolute difference `1.7763568394002505e-15`
- Conclusion:
  - interpolation math is not the drift source
  - the drift comes from the inflow deep ownership path after value evaluation
  - no new accepted exact result from this blocker in its current form

## Next

- Stop pushing this external-boundary-deep family as an accepted exact candidate.
- If we continue from the accepted exact path, the next single blocker should be
  chosen outside the rejected refresh/fullstep/build-flag/external-deep family.
- Most likely next point: `Assemble_Flux_2` ownership pushdown, subject to a new
  accepted-only audit from the accepted checkpoint.
