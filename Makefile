.PHONY: dev setup backend frontend clean

# One-command setup
setup:
	@bash setup.sh

# Start both backend and frontend
dev:
	@echo "Starting backend on http://localhost:8000 ..."
	@echo "Starting frontend on http://localhost:3000 ..."
	@trap 'kill 0' EXIT; \
	  .venv/bin/uvicorn backend.main:app --reload --port 8000 & \
	  cd frontend && npm run dev & \
	  wait

# Start backend only
backend:
	.venv/bin/uvicorn backend.main:app --reload --port 8000

# Start frontend only
frontend:
	cd frontend && npm run dev

# Clean generated files
clean:
	rm -rf data/vectors data/papers data/*.db
	rm -rf frontend/node_modules frontend/dist
	rm -rf .venv __pycache__ backend/__pycache__
