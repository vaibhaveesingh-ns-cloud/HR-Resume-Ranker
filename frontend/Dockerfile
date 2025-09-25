# Frontend Dockerfile: Build Vite app and serve with Nginx

# --- Build stage ---
FROM node:20 AS build
  WORKDIR /app

# Install dependencies
COPY package.json ./
# Avoid rollup native optional binary resolution issues on some platforms
ENV ROLLUP_SKIP_NODEJS_NATIVE=1
# Install and generate a fresh lockfile for the container's platform (allows optional deps)
RUN npm install --no-package-lock \
 && npm install -D rollup@4.17.2

# Copy source
COPY . .

# Build-time API base (overridable in docker-compose via build args)
ARG VITE_API_BASE=/api
ENV VITE_API_BASE=${VITE_API_BASE}

# Build static site (ensure JS fallback during this step)
RUN ROLLUP_SKIP_NODEJS_NATIVE=1 npm run build

# --- Runtime stage ---
FROM nginx:alpine AS runtime

# Copy Nginx config with /api proxy to backend
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
