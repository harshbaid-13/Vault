#!/usr/bin/env bash
# Back up the running vault: a database snapshot plus any new files into ./backups.
#   ./backup.sh                  a backup (what cron runs every night)
#   ./backup.sh --verify         re-read every backed-up file and check it (monthly; slow)
#   ./backup.sh --prune-mirror   delete backed-up files no kept snapshot needs
# Exit code is 0 only when the backup is complete. See README.md → Backup.
set -euo pipefail
cd "$(dirname "$0")"
# cron starts with a bare PATH; docker lives in /usr/bin on Ubuntu.
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
echo "== $(date '+%Y-%m-%d %H:%M:%S') backup $*"
docker compose exec -T vault python -m app.backup "$@"
