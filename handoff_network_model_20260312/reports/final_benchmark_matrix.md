# Final Benchmark Matrix

## Policy

- single-process only
- no multiprocessing or threading in any benchmark on this branch
- only evolve/model time counts toward the headline performance conclusion

## Current Matrix

| Line | Flags | Case | Evolve/Model Time (s) | Evolve Wall (s) | Allclose | Notes |
|---|---|---|---:|---:|---|---|
| serial Python baseline | none | 10m | 4.743990 | 4.818651 | baseline | `reports/serial_python_10m_noprof_summary.json` |
| serial Python baseline | none | 2h | 35.700089 | 35.925078 | baseline | `reports/serial_python_2h_noprof_summary.json` |
| serial Python baseline | none | 40h | 562.262618 | 565.037927 | baseline | `reports/serial_python_40h_noprof_summary.json` |
| Cython nodechain | `ISLAM_USE_CYTHON_NODECHAIN=1` | 10m | 4.591877 | 4.665236 | true | `reports/cython_nodechain_10m_noprof_v2_compare.json` |
| Cython nodechain | `ISLAM_USE_CYTHON_NODECHAIN=1` | 2h | 34.740252 | 34.955405 | true | `reports/cython_nodechain_2h_noprof_v2_compare.json` |
| Cython Roe | `ISLAM_USE_CYTHON_ROE_FLUX=1` | 10m | 1.635677 | 1.710775 | true | `reports/cython_roe_flux_10m_hit_v2b_compare.json` |
| Cython update-cell | `ISLAM_USE_CYTHON_UPDATE_CELL=1` | 10m | 1.530594 | 1.604467 | false | fast but drifting |
| exact candidate | `NODECHAIN=1, ROE=1, UPDATE=0` | 10m | 1.451734 | 1.523346 | true | `reports/cython_nodechain_roe_10m_hit_compare.json` |
| exact candidate | `NODECHAIN=1, ROE=1, UPDATE=0` | 2h | 11.496324 | 11.741119 | true | `reports/cython_nodechain_roe_2h_hit_compare.json` |
| exact candidate | `NODECHAIN=1, ROE=1, UPDATE=0` | 40h | 213.933772 | 217.559511 | true | `reports/cython_nodechain_roe_40h_exact_compare.json` |
