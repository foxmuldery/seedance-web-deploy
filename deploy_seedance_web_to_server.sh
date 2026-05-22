#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-207.148.106.142}"
USER_NAME="${2:-root}"
REMOTE_DIR="${3:-/opt/seedance-web}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE="${USER_NAME}@${HOST}"

required_files=(
  "volcengine_seedance_web.py"
  "requirements-seedance-web.txt"
  "Dockerfile.seedance-web"
  "docker-compose.seedance-web.yml"
  ".env.seedance-web.example"
)

upload_files=("${required_files[@]}")
if [[ -f "${SCRIPT_DIR}/.env.seedance-web" ]]; then
  upload_files+=(".env.seedance-web")
fi

for file in "${required_files[@]}"; do
  if [[ ! -f "${SCRIPT_DIR}/${file}" ]]; then
    echo "Missing required file: ${file}" >&2
    exit 1
  fi
done

ssh -o StrictHostKeyChecking=accept-new "${REMOTE}" "mkdir -p '${REMOTE_DIR}'"
tar -C "${SCRIPT_DIR}" -czf - "${upload_files[@]}" | ssh "${REMOTE}" "tar -xzf - -C '${REMOTE_DIR}'"

ssh "${REMOTE}" "cd '${REMOTE_DIR}' && if [ ! -f .env.seedance-web ]; then cp .env.seedance-web.example .env.seedance-web; fi"

if [[ ! -f "${SCRIPT_DIR}/.env.seedance-web" ]]; then
  cat <<EOF
Files uploaded to ${REMOTE}:${REMOTE_DIR}

Next, edit the server env file and fill real keys:
  ssh ${REMOTE}
  cd ${REMOTE_DIR}
  nano .env.seedance-web
  docker compose -f docker-compose.seedance-web.yml up -d --build

Then open:
  http://${HOST}:8080/
EOF
  exit 0
fi

ssh "${REMOTE}" "cd '${REMOTE_DIR}' && docker compose -f docker-compose.seedance-web.yml up -d --build"

echo "Deployed: http://${HOST}:8080/"
