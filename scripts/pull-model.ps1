param([string]$Model = "llama3.2:3b")
docker compose exec ollama ollama pull $Model
