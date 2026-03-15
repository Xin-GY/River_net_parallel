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

- Headline command:
  - `conda run -n python311 python tools/profile_islam_evolve_only.py --case-name serial_python_10m_noprof --sim-end-time '2024-01-01 00:10:00' --output-dir result/serial_python_10m_noprof --summary-json reports/serial_python_10m_noprof_summary.json`
- Output directory:
  - `result/serial_python_10m_noprof`
- Headline summary:
  - evolve/model time: `4.743990 s`
  - evolve wall time: `4.818651 s`
  - total steps: `181`
- Separate profiling command used only for hotspot attribution:
  - `conda run -n python311 python tools/profile_islam_evolve_only.py --case-name serial_python_10m_loop_only --sim-end-time '2024-01-01 00:10:00' --output-dir result/serial_python_10m_loop_only --summary-json reports/serial_python_10m_loop_only_summary.json --profile-out reports/serial_python_10m_loop_only.prof`

## Representative Long Case

Hotspot attribution still uses the profiled 2-hour run, but the benchmark headline stays on no-profile evolve timing.

- Case duration:
  - `2h`
- Headline command:
  - `conda run -n python311 python tools/profile_islam_evolve_only.py --case-name serial_python_2h_noprof --sim-end-time '2024-01-01 02:00:00' --output-dir result/serial_python_2h_noprof --summary-json reports/serial_python_2h_noprof_summary.json`
- Output directory:
  - `result/serial_python_2h_noprof`
- Headline summary:
  - evolve/model time: `35.700089 s`
  - evolve wall time: `35.925078 s`
  - total steps: `1482`
- Separate profiling command used only for hotspot attribution:
  - `conda run -n python311 python tools/profile_islam_evolve_only.py --case-name serial_python_2h_loop_only --sim-end-time '2024-01-01 02:00:00' --output-dir result/serial_python_2h_loop_only --summary-json reports/serial_python_2h_loop_only_summary.json --profile-out reports/serial_python_2h_loop_only.prof`

## Full 40-Hour Serial Baseline

- Headline command:
  - `conda run -n python311 python tools/profile_islam_evolve_only.py --case-name serial_python_40h_noprof --sim-end-time '2024-01-02 16:00:00' --output-dir result/serial_python_40h_noprof --summary-json reports/serial_python_40h_noprof_summary.json`
- Output directory:
  - `result/serial_python_40h_noprof`
- Headline summary:
  - evolve/model time: `562.262618 s`
  - evolve wall time: `565.037927 s`
  - total steps: `29783`

## Raw Benchmark Artifacts

- 10-minute no-profile summary:
  - `reports/serial_python_10m_noprof_summary.json`
- 10-minute summary:
  - `reports/serial_python_10m_loop_only_summary.json`
- 10-minute profile:
  - `reports/serial_python_10m_loop_only.prof`
- 10-minute profile summary:
  - `reports/serial_python_10m_loop_only_profile_summary.json`
- 2-hour no-profile summary:
  - `reports/serial_python_2h_noprof_summary.json`
- 2-hour summary:
  - `reports/serial_python_2h_loop_only_summary.json`
- 2-hour profile:
  - `reports/serial_python_2h_loop_only.prof`
- 2-hour profile summary:
  - `reports/serial_python_2h_loop_only_profile_summary.json`
- 40-hour no-profile summary:
  - `reports/serial_python_40h_noprof_summary.json`

## Baseline Conclusion

For this branch, the meaningful baseline is not the script end-to-end wall time of `Islam.py`, but the prepared evolve-loop wall/model time above. All later Cython before/after numbers should be compared against these no-profile evolve-only serial baselines, while `cProfile` runs are used only to rank hotspots.
