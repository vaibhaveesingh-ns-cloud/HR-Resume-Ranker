# Backend Dockerfile: FastAPI + Uvicorn
# Small, production-ready Python image
FROM python:3.11-slim AS base

# Avoid Python buffering and write bytecode
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system deps required by pdfminer/pypdf/docx and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app/backend

# Install Python dependencies first (better layer caching)
COPY requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY . /app/backend/

# Expose FastAPI port
EXPOSE 8000

# Default command (can be overridden by docker-compose)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
