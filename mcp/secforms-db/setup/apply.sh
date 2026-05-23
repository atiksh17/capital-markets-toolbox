#!/usr/bin/env bash
# Apply 01_create_role.sql then 02_verify.sql against the sec-postgres container.
# Reads the secforms_ro password from $SECFORMS_RO_PASSWORD or generates a new one.
# Prints the password to stdout (capture it for the MCP env file).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

: "${PG_HOST:=127.0.0.1}"
: "${PG_PORT:=54324}"
: "${PG_DB:=secforms}"
: "${PG_SUPERUSER:=sec_admin}"

if [[ -z "${PG_SUPERUSER_PASSWORD:-}" ]]; then
  echo "PG_SUPERUSER_PASSWORD must be set (the sec_admin password)." >&2
  exit 1
fi

if [[ -z "${SECFORMS_RO_PASSWORD:-}" ]]; then
  SECFORMS_RO_PASSWORD="$(openssl rand -base64 32 | tr -d '\n=' | tr '+/' '-_')"
  echo "Generated new password for secforms_ro:" >&2
fi
echo "SECFORMS_RO_PASSWORD=${SECFORMS_RO_PASSWORD}"

echo "Applying 01_create_role.sql ..." >&2
PGPASSWORD="${PG_SUPERUSER_PASSWORD}" psql \
  -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_SUPERUSER}" -d "${PG_DB}" \
  -v ON_ERROR_STOP=1 \
  -v ro_password="'${SECFORMS_RO_PASSWORD}'" \
  -f "${SCRIPT_DIR}/01_create_role.sql"

echo "Running 02_verify.sql as secforms_ro ..." >&2
PGPASSWORD="${SECFORMS_RO_PASSWORD}" psql \
  -h "${PG_HOST}" -p "${PG_PORT}" -U secforms_ro -d "${PG_DB}" \
  -f "${SCRIPT_DIR}/02_verify.sql" || true

echo "Done. Save the SECFORMS_RO_PASSWORD value above into your MCP env file." >&2
