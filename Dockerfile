# Single-container Dockerfile for Elastic Beanstalk
# Builds frontend with Node, installs backend in Python, runs both via supervisord

# ---- Frontend build stage ----
FROM node:20 AS fe-build
WORKDIR /frontend
# Avoid rollup native optional binary resolution issues on some platforms
ENV ROLLUP_SKIP_NODEJS_NATIVE=1
COPY frontend/package*.json ./
# Install dependencies (use npm ci if lockfile present, fallback to install)
RUN npm install --no-package-lock \
 && npm install -D rollup@4.17.2
# Copy source and build
COPY frontend/ .
ARG VITE_API_BASE=/api
ENV VITE_API_BASE=${VITE_API_BASE}
RUN ROLLUP_SKIP_NODEJS_NATIVE=1 npm run build

# ---- Final runtime stage ----
FROM python:3.11-slim AS runtime

# System deps for backend and Nginx + Supervisor
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    poppler-utils \
    nginx \
    supervisor \
 && rm -rf /var/lib/apt/lists/*

# Backend setup
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend/ /app/backend/

# Frontend static site into Nginx html root
COPY --from=fe-build /frontend/dist /usr/share/nginx/html

# Nginx config (proxy /api to local uvicorn)
COPY frontend/deploy/nginx.conf /etc/nginx/conf.d/default.conf
# Adjust upstream to point to localhost since both processes are in the same container
RUN sed -i 's|http://backend:8000/|http://127.0.0.1:8000/|g' /etc/nginx/conf.d/default.conf

# Supervisor config to run both Nginx and Uvicorn
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 80
CMD ["/usr/bin/supervisord", "-n"]
