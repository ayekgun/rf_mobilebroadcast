#!/usr/bin/env bash
# ==============================================================================
# Robot Framework Standard Runner for Anti-Fraud JNS7 CMS
# Zero Truncation (--maxassignlength 0) | Clean BDD | 12-Column CSV Listener
# ==============================================================================
set -e

REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "$REAL_SCRIPT")"
RF_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$RF_DIR"

export DISPLAY="${DISPLAY:-:0}"

ROBOT_ARGS=()
for arg in "$@"; do
  if [ "$arg" == "--headed" ] || [ "$arg" == "--watch" ]; then
    export HEADED=1
  elif [[ "$arg" == rf_mobilebroadcast/* ]]; then
    # Strip rf_mobilebroadcast/ prefix if caller was in parent directory
    ROBOT_ARGS+=("${arg#rf_mobilebroadcast/}")
  else
    ROBOT_ARGS+=("$arg")
  fi
done

if [ ${#ROBOT_ARGS[@]} -eq 0 ]; then
  ROBOT_ARGS=("tests")
fi

echo "========================================================================"
echo " Starting Robot Framework Automation Suite: rf_mobilebroadcast"
echo " Target: ${ROBOT_ARGS[*]}"
echo " Headed Mode: ${HEADED:-0} (1=Foreground Live Watch, 0=Background Headless)"
echo " Options: --maxassignlength 0 | --listener libraries/CsvListener.py | --outputdir results"
echo "========================================================================"

mkdir -p results

python3 -m robot \
  --pythonpath libraries \
  --listener libraries/CsvListener.py \
  --maxassignlength 0 \
  --outputdir results \
  "${ROBOT_ARGS[@]}"
