# release / start 는 railway.json deploy 섹션 (preDeployCommand / startCommand) 으로 이전.
# Procfile 잔재 — Heroku 호환·로컬 doc 용. Railway 는 railway.json 우선.
release: bash scripts/run_migrations.sh
web: uv run uvicorn server.main:app --host 0.0.0.0 --port $PORT
