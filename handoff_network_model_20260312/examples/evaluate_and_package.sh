#!/usr/bin/env bash
set -euo pipefail

mkdir -p /tmp/mplconfig
MPLCONFIGDIR=/tmp/mplconfig conda run -n python310 python result/eval_river11_nse.py result/exp_handoff_run

MPLCONFIGDIR=/tmp/mplconfig conda run -n python310 python result/package_river11_report.py result/exp_handoff_run
