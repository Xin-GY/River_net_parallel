# Assemble Deep Exact Error Report

## Scope

- branch: `feature/cpp-exact-accepted-after-assemble-reaudit`
- baseline accepted exact checkpoint: `feature/cpp-exact-accepted-reaudit-next@9a7c094`
- candidate flag under test:
  - `ISLAM_CPP_USE_ASSEMBLE_DEEP=1`

## Strict Compare Results

| Case | Compare report | allclose | max_abs | max_rel |
| --- | --- | --- | ---: | ---: |
| 10m | `reports/assemble_deep_10m_compare.json` | `true` | `0.0` | `0.0` |
| 2h | `reports/assemble_deep_2h_compare.json` | `true` | `0.0` | `0.0` |
| 40h | `reports/assemble_deep_40h_compare.json` | `true` | `0.0` | `0.0` |

## History Files

| Case | `cfl_history.csv` rows | `internal_node_history.csv` rows | First diff |
| --- | ---: | ---: | --- |
| 10m | `182 / 182` | `181 / 181` | none |
| 2h | `1483 / 1483` | `1482 / 1482` | none |
| 40h | `29784 / 29784` | `29783 / 29783` | none |

## Conclusion

The deeper assemble path is exact on all three gate cases.

- no drift was observed in `cfl_history.csv`
- no drift was observed in `internal_node_history.csv`
- the branch fails the acceptance gate only on performance, not on correctness
