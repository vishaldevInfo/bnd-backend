
.PHONY: venv install setup dev backend frontend frontend-install frontend-dev clean

# ---------- Backend (FastAPI) ----------

# Create Python virtual environment
venv:
	python3 -m venv venv

# Install backend dependencies
install:
	./venv/bin/python -m pip install -r backend/requirements.txt

# Setup backend
setup: venv install

# Run FastAPI backend
backend:
	cd backend && ../venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload

# ---------- Frontend (Next.js) ----------

# Install frontend dependencies
frontend-install:
	cd frontend && npm install

# Run Next.js development server
frontend-dev:
	cd frontend && npm run dev

# Setup both backend and frontend
install-all: setup frontend-install

# Run backend
dev: backend

# Remove generated dependencies and virtual environment
clean:
	rm -rf venv frontend/node_modules
