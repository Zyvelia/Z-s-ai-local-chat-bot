#!/usr/bin/env bash
set -euo pipefail
mkdir -p backups
out="backups/character-chat-$(date -u +%Y%m%d-%H%M%S).dump"
docker compose exec -T postgres pg_dump -U character -d character_chat -Fc > "$out"
echo "Backup: $out"
