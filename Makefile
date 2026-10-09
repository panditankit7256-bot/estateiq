.PHONY: up down test backend-test frontend-test dev-api dev-web report
up:            ; docker compose up --build
down:          ; docker compose down -v
test: backend-test frontend-test
backend-test:  ; cd backend && python -m pytest -q
frontend-test: ; cd frontend && npm run typecheck && npm test
dev-api:       ; cd backend && uvicorn app.main:app --reload --port 8000
dev-web:       ; cd frontend && npm install && npm run dev
report:        ; cd backend && python ../scripts/model_report.py
