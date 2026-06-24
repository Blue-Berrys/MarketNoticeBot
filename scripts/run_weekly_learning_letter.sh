#!/usr/bin/env bash
set -euo pipefail

# Saturday beginner finance-learning letter. Light companion to the Wednesday
# market notice: one LLM call, no multi-agent deep run.

APP_DIR="${HOME}/weekly-snapshot"
REPO_DIR="${HOME}/TradingAgents"
LOG_DIR="${APP_DIR}/logs"
mkdir -p "${LOG_DIR}"

run_learning_letter() {
  cd "${REPO_DIR}"
  set -a
  # shellcheck disable=SC1091
  source "${REPO_DIR}/.env"
  set +a
  export HTTP_PROXY="http://127.0.0.1:7897"
  export HTTPS_PROXY="http://127.0.0.1:7897"
  export ALL_PROXY="socks5://127.0.0.1:7897"

  "${REPO_DIR}/.venv/bin/python" scripts/weekly_learning_letter.py \
    --config "${APP_DIR}/feishu.env" \
    --progress "${APP_DIR}/learning-progress.json" \
    --output "${APP_DIR}/latest-learning-letter.md"
}

export -f run_learning_letter
export APP_DIR REPO_DIR LOG_DIR

exec /usr/bin/flock -n "${APP_DIR}/weekly-learning.lock" \
  /bin/bash -c run_learning_letter \
  >> "${LOG_DIR}/weekly-learning.log" 2>&1
