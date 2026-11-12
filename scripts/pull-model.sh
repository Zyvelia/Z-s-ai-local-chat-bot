#!/usr/bin/env sh
set -eu
docker compose exec ollama ollama pull "${1:-llama3.2:3b}"
