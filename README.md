# HR/TA Resume Ranker – Dockerized Setup

This repository contains:
- Frontend: React (Vite), served by Nginx in production.
- Backend: FastAPI (Python), exposes REST APIs, file upload, and artifact endpoints.

You can run a production-like stack locally with Docker Compose, or run the services directly during development.

## Prerequisites
- Docker Desktop (or Docker Engine) and Docker Compose
- OpenAI API key (for backend)

## Run with Docker Compose
1) Build and start:
```bash
docker-compose up --build
```
This will:
- Build the frontend and serve it via Nginx (port 80)
- Build and run the FastAPI backend (port 8000, Swagger UI at /docs)

2) Open the app:
- Frontend (Nginx): http://localhost
- Backend API docs (FastAPI): http://localhost:8000/docs

### How it’s wired
- Frontend-to-backend calls use `VITE_API_BASE` (default “/api” via `docker-compose.yml`) and are proxied by Nginx (see `deploy/nginx.conf`).
- The backend (`backend/main.py`) allows CORS for local dev; in Docker the frontend goes through Nginx, so browser calls go to `/api`.

### Environment variables
- Backend (configure via Compose env or your shell):
  - `OPENAI_API_KEY` (required)
  - `OPENAI_TIMEOUT` (optional, default 60)
  - `MAX_RESUME_CHARS` (optional, default 8000)
  - `MAX_TOTAL_RESUME_CHARS` (optional, default 40000)
  - `GITHUB_TOKEN` (optional, raises GitHub API limits)
- Frontend build-time:
  - `VITE_API_BASE` (default “/api” in Compose; for local dev without Docker, set `http://127.0.0.1:8000`)

## Local Development (without Docker)
- Backend (FastAPI)
```bash
# From project root
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
pip install -r backend/requirements.txt
export OPENAI_API_KEY=your_key_here
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
# Visit http://127.0.0.1:8000/docs
```

- Frontend (Vite)
```bash
# From project root
npm install
# Create .env with API pointing to FastAPI
echo "VITE_API_BASE=http://127.0.0.1:8000" > .env
npm run dev
# Visit http://127.0.0.1:5173
```

## Project Structure
- `backend/` – FastAPI app and utilities
- `deploy/nginx.conf` – Nginx config (serves frontend, proxies “/api” to backend)
- `Dockerfile.frontend` – Frontend build + Nginx runtime image
- `backend/Dockerfile` – Backend container image
- `docker-compose.yml` – Orchestrates frontend and backend services

## Create a ZIP for AWS Elastic Beanstalk (Multi‑Container Docker)
Elastic Beanstalk (EB) supports multi-container Docker environments via ECS using a `Dockerrun.aws.json` v2 file that references images hosted in ECR.

High-level steps:
1. Build and push images (frontend and backend) to ECR.
2. Create `Dockerrun.aws.json` that points to those ECR images.
3. Zip the `Dockerrun.aws.json` and upload the ZIP in the EB console.

### 1) Build and push images to Amazon ECR
Create two ECR repos (or reuse existing):
- `YOUR_AWS_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com/hr-resume-frontend`
- `YOUR_AWS_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com/hr-resume-backend`

Login and push (replace placeholders locally when you run):
```bash
aws ecr get-login-password --region YOUR_REGION \
  | docker login --username AWS --password-stdin YOUR_AWS_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com

# Frontend
docker build -t hr-resume-frontend -f Dockerfile.frontend .
docker tag hr-resume-frontend:latest YOUR_AWS_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com/hr-resume-frontend:latest
docker push YOUR_AWS_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com/hr-resume-frontend:latest

# Backend
docker build -t hr-resume-backend -f backend/Dockerfile .
docker tag hr-resume-backend:latest YOUR_AWS_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com/hr-resume-backend:latest
docker push YOUR_AWS_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com/hr-resume-backend:latest
```

### 2) Create `Dockerrun.aws.json` (v2) at repo root
Use placeholders so you don’t need to commit secrets. EB environment properties will hold real values.

```json
{
  "AWSEBDockerrunVersion": 2,
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "YOUR_AWS_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com/hr-resume-backend:latest",
      "essential": true,
      "memory": 512,
      "portMappings": [{ "containerPort": 8000, "hostPort": 8000 }],
      "environment": [
        { "name": "OPENAI_API_KEY", "value": "SET_IN_EB_ENV_VARS" },
        { "name": "OPENAI_TIMEOUT", "value": "120" },
        { "name": "MAX_RESUME_CHARS", "value": "6000" },
        { "name": "MAX_TOTAL_RESUME_CHARS", "value": "30000" }
      ]
    },
    {
      "name": "frontend",
      "image": "YOUR_AWS_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com/hr-resume-frontend:latest",
      "essential": true,
      "memory": 256,
      "portMappings": [{ "containerPort": 80, "hostPort": 80 }],
      "environment": [{ "name": "VITE_API_BASE", "value": "/api" }],
      "links": ["backend"]
    }
  ]
}
```

### 3) Create the ZIP bundle and upload to Elastic Beanstalk
- EB expects `Dockerrun.aws.json` at the root of the ZIP.

Create the ZIP:
```bash
zip -r beanstalk-bundle.zip Dockerrun.aws.json
```

Then:
- In AWS Elastic Beanstalk Console:
  - Create a new app (Platform: Multi-container Docker) or update an existing one.
  - Upload `beanstalk-bundle.zip` as a new version and deploy.

Tips:
- If your EB environment uses a Load Balancer, ensure external port 80 maps to the frontend container’s port 80.
- The backend port 8000 can remain internal; the frontend proxies to it via Nginx (`/api`).

## Troubleshooting
- Frontend Docker build errors (Rollup native binaries on Apple Silicon/Docker):
  - We added mitigations in `Dockerfile.frontend`. If issues persist:
    - Build frontend on host (`npm run build`) and use a runtime‑only Nginx image that copies `dist/`.
    - Or build images on linux/amd64 and push to ECR.
- Browser shows “TypeError: Failed to fetch”:
  - Ensure the backend is running and reachable at the URL set by `VITE_API_BASE`.
  - In Docker Compose, the frontend calls “/api,” which Nginx proxies to backend.
