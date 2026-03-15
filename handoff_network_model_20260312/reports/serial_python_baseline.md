# Serial Python Baseline

This branch measures only the single-process, exact, non-FAST route.

## Measurement Policy

- `ISLAM_USE_PARALLEL=0`
- `ISLAM_FAST_MODE=0`
- headline time uses evolve-only timing
- initialization, Fine preprocessing, section-table construction, and other pre-loop setup are excluded from the measured `model/evolve time`
- the evolve-only benchmark is driven by:
  - `Islam.prepare_net_for_evolve(...)`
  - `Islam.run_prepared_evolve(...)`
  - so the timed scope is the `_evolve_base(...)` loop body only

## 10-Minute Case

- Command:
  - `conda run -n python311 python tools/profile_islam_evolve_only.py --case-name serial_python_10m_loop_only --sim-end-time '2024-01-01 00:10:00' --output-dir result/serial_python_10m_loop_only --summary-json reports/serial_python_10m_loop_only_summary.json --profile-out reports/serial_python_10m_loop_only.prof`
- Output directory:
  - `result/serial_python_10m_loop_only`
- Summary:
  - evolve/model time: `10.744231 s`
  - evolve wall time: `10.843292 s`
  - total steps: `181`

## Representative Long Case

Full 40h serial pure-Python profiling on this branch is expected to be expensive enough to block iteration during the Cython implementation loop, so hotspot identification uses a longer representative serial run:

- Case duration:
  - `2h`
- Command:
  - `conda run -n python311 python tools/profile_islam_evolve_only.py --case-name serial_python_2h_loop_only --sim-end-time '2024-01-01 02:00:00' --output-dir result/serial_python_2h_loop_only --summary-json reports/serial_python_2h_loop_only_summary.json --profile-out reports/serial_python_2h_loop_only.prof`
- Output directory:
  - `result/serial_python_2h_loop_only`
- Summary:
  - evolve/model time: `81.464443 s`
  - evolve wall time: `81.598773 s`
  - total steps: `1482`

## Raw Benchmark Artifacts

- 10-minute summary:
  - `reports/serial_python_10m_loop_only_summary.json`
- 10-minute profile:
  - `reports/serial_python_10m_loop_only.prof`
- 10-minute profile summary:
  - `reports/serial_python_10m_loop_only_profile_summary.json`
- 2-hour summary:
  - `reports/serial_python_2h_loop_only_summary.json`
- 2-hour profile:
  - `reports/serial_python_2h_loop_only.prof`
- 2-hour profile summary:
  - `reports/serial_python_2h_loop_only_profile_summary.json`

## Baseline Conclusion

For this branch, the meaningful baseline is not the script end-to-end wall time of `Islam.py`, but the prepared evolve-loop wall/model time above. All later Cython before/after numbers should be compared against these evolve-only serial baselines.
