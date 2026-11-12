#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 1 ]; then echo "Usage: $0 backups/FILE.dump" >&2; exit 2; fi
# Destructive restore: intended for a fresh EMPTY test database only.
read -r -p "Restore to EMPTY character_chat database? Type RESTORE: " response
[ "$response" = RESTORE ] || exit 1
docker compose exec -T postgres pg_restore --exit-on-error --no-owner -U character -d character_chat < "$1"
