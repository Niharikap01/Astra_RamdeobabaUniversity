.PHONY: help install train test run-backend run-dashboard docker-up docker-down clean

help:
	@echo "NightWatch: A Sleep-Aware Digital Twin for Proactive Hypertension Risk Prediction"
	@echo "----------------------------------------------------------------------------------"
	@echo "make install         Install backend, ML, and dashboard dependencies"
	@echo "make train           Train LightGBM model, calibrate, run ablation, and save artifacts"
	@echo "make test            Run backend test suite with coverage"
	@echo "make run-backend     Start FastAPI backend server (port 8000)"
	@echo "make run-dashboard   Start React + Vite dashboard (port 5173)"
	@echo "make docker-up       Build and run entire stack via docker-compose"
	@echo "make docker-down     Tear down docker containers"
	@echo "make clean           Remove caches, test artifacts, and compiled bytecode"

install:
	pip install -r backend/requirements.txt
	pip install -r ml/requirements.txt
	cd dashboard && npm install

train:
	python -m ml.train_lightgbm

evaluate:
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/evaluate.ps1


test:
	pytest backend/tests -v --cov=backend/app --cov-report=term-missing

run-backend:
	uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

run-dashboard:
	cd dashboard && npm run dev

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov ml/artifacts/*.png
