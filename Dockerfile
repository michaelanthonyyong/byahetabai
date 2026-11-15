# eNaviga — single service: FastAPI backend + built React frontend.
# Runs on any Docker host (Render, Railway, Fly.io, a VPS...).
# All configuration comes from environment variables at runtime (see DEPLOY.md).

# ---- 1. Build the React app ------------------------------------------------
FROM node:20-bookworm-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/yarn.lock ./
RUN yarn install --frozen-lockfile --network-timeout 600000
COPY frontend/ ./
# Empty on purpose: the app calls the API on whatever address serves it.
ENV REACT_APP_BACKEND_URL="" \
    GENERATE_SOURCEMAP=false
RUN yarn build

# ---- 2. Python runtime -------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app/backend
COPY backend/requirements.txt ./
# emergentintegrations lives on Emergent's private index and isn't imported.
RUN grep -v '^emergentintegrations' requirements.txt > /tmp/requirements.txt \
 && pip install -r /tmp/requirements.txt
COPY backend/ ./
COPY --from=web /web/build /app/frontend/build
ENV FRONTEND_DIST=/app/frontend/build \
    PORT=8000
EXPOSE 8000
# --proxy-headers: the host's HTTPS proxy sits in front of us.
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
