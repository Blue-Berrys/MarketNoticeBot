#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${HOME}/weekly-snapshot"
REPO_DIR="${HOME}/TradingAgents"
LOG_DIR="${APP_DIR}/logs"
mkdir -p "${LOG_DIR}"

run_weekly_report() {
  cd "${REPO_DIR}"
  set -a
  # shellcheck disable=SC1091
  source "${REPO_DIR}/.env"
  set +a
  export HTTP_PROXY="http://127.0.0.1:7897"
  export HTTPS_PROXY="http://127.0.0.1:7897"
  export ALL_PROXY="socks5://127.0.0.1:7897"

  # Build the snapshot first; it fetches dated rows from reliable CN-accessible
  # sources (Sina/Tencent). Derive the analysis date from the snapshot itself
  # instead of a separate, flaky yfinance call that can return an empty string
  # at cron time and silently break the whole deep run (--date "").
  local staging="${APP_DIR}/deep-output/snapshot.txt"
  mkdir -p "${APP_DIR}/deep-output"
  "${REPO_DIR}/.venv/bin/python" scripts/weekly_market_snapshot.py \
    --config "${APP_DIR}/feishu.env" \
    --print-only \
    --output "${staging}"

  local analysis_date
  analysis_date="$(grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' "${staging}" | head -1)"
  if ! [[ "${analysis_date}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "ERROR: could not derive analysis_date from snapshot; aborting" >&2
    return 1
  fi
  local output_dir="${APP_DIR}/deep-output/${analysis_date}"
  mkdir -p "${output_dir}"
  mv "${staging}" "${output_dir}/snapshot.txt"

  local deep_status=0
  "${REPO_DIR}/.venv/bin/python" scripts/run_weekly_deep_analysis.py \
    --date "${analysis_date}" \
    --output-dir "${output_dir}" \
    --max-workers 3 || deep_status=$?

  "${REPO_DIR}/.venv/bin/python" scripts/compile_weekly_learning_report.py \
    --date "${analysis_date}" \
    --summary "${output_dir}/summary_${analysis_date}.json" \
    --snapshot "${output_dir}/snapshot.txt" \
    --output "${APP_DIR}/latest-learning-report.md" \
    --feishu-config "${APP_DIR}/feishu.env"

  return "${deep_status}"
}

export -f run_weekly_report
export APP_DIR REPO_DIR LOG_DIR

exec /usr/bin/flock -n "${APP_DIR}/weekly-snapshot.lock" \
  /bin/bash -c run_weekly_report \
  >> "${LOG_DIR}/weekly-snapshot.log" 2>&1
