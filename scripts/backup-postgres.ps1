# Run from repository root; requires a running Docker Compose PostgreSQL service.
param([string]$Destination = "backups")
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$path = Join-Path $Destination "character-chat-$timestamp.dump"
# Use cmd.exe binary output redirection for consistent binary pg_dump output on Windows PowerShell 5.1.
$dest = [System.IO.Path]::GetFullPath($path)
$cmd = "docker compose exec -T postgres pg_dump -U character -d character_chat -Fc > `"$dest`""
cmd.exe /d /c $cmd
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed; do not rely on $dest" }
Write-Output "Backup: $dest"
