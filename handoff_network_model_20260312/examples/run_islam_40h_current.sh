#!/usr/bin/env bash
set -euo pipefail

mkdir -p /tmp/mplconfig
MPLCONFIGDIR=/tmp/mplconfig ISLAM_OUTPUT_PATH=result/exp_handoff_run ISLAM_SIM_END_TIME='2024-01-02 16:00:00' ISLAM_OUTPUT_RIVERS=river11 ISLAM_USE_FINE_INTERPOLATION=0 conda run -n python310 python Islam.py
