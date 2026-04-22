# ---------- Frontend build ----------
FROM node:20-bookworm-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend .
RUN npm run build

# ---------- Backend runtime ----------
FROM python:3.11-slim
WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Hugging Face Spaces expone PORT (fallback 7860)
ENV PORT=7860
EXPOSE 7860

CMD sh -c "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"
