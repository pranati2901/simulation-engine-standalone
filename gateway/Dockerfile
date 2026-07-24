# Gateway = built SimCore SPA served by nginx, which also reverse-proxies to both engines.
# Build context is the repo root (so it can see both frontend/ and gateway/).

# ---- stage 1: build the SimCore frontend (includes the embedded cyber app) ----
FROM node:20-slim AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
# VITE_API_KEY (from frontend/.env, copied above) is embedded here; it must match the
# SimCore engine's SCENARIO_API_KEY set in docker-compose.yml.
RUN npm run build

# ---- stage 2: nginx serving the build + routing ----
FROM nginx:alpine
COPY gateway/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
