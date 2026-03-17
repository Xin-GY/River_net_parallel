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
