# Railway 는 railway.json deploy 섹션 (preDeployCommand / startCommand) 사용.
# release: 라인 제거 — nixpacks 가 build phase 안의 RUN 으로 잘못 변환하던 문제 회피.
# web: 만 남김 (Heroku 호환·문서 용 — Railway 는 railway.json 우선).
web: uv run uvicorn server.main:app --host 0.0.0.0 --port $PORT
