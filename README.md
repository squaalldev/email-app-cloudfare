---
license: apache-2.0
title: Chatbot Email App
sdk: docker
emoji: ⚡
colorFrom: green
colorTo: red
short_description: Write emails with Gemini
---
# Chatbot Email App - React + FastAPI

Aplicación de chat para generar emails narrativos con Gemini.

## Stack
- Frontend: React + TypeScript + Vite
- Backend: FastAPI
- IA: Google Gemini (`google-genai`)

## Desarrollo local

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Frontend en `http://localhost:3000` y backend en `http://localhost:8000`.

## Variables de entorno

### Backend
- `GOOGLE_API_KEY` (requerida)
- `GEMINI_MODEL` (opcional, default: `gemini-2.5-flash`)
- `APP_DATA_DIR` (opcional, default: `backend/data`)

## Deploy en Hugging Face Spaces (Docker)

1. Crea un Space tipo **Docker**.
2. Sube este repositorio.
3. En **Settings → Secrets**, agrega:
   - `GOOGLE_API_KEY`
4. (Opcional) agrega `GEMINI_MODEL`.

> Sí, en HF puedes inyectar el secret directamente y esta app lo toma desde `os.environ["GOOGLE_API_KEY"]` en runtime.

## Endpoints API
- `GET /api/health`
- `GET /api/chats`
- `POST /api/chats`
- `GET /api/chats/{chat_id}/messages`
- `POST /api/chats/{chat_id}/messages`
- Compatibilidad legacy: `POST /api/chat/send`

## Cloudflare + Gemini

Consulta la guía de integración en [`CLOUDFARE_GEMINI_REACT.md`](./CLOUDFARE_GEMINI_REACT.md).

## Deploy en Cloudflare (recomendado)

### 1) Backend API en Cloudflare Workers

Este repo incluye un Worker en `cloudflare/worker-api` con los mismos endpoints base usados por React (`/api/chats`, `/api/chats/{id}/messages`, etc.) y almacenamiento en KV.

```bash
cd cloudflare/worker-api
npm install
```

Crear KV namespace y pegar el ID en `wrangler.toml`:

```bash
npx wrangler kv namespace create CHAT_KV
```

Configurar secretos:

```bash
npx wrangler secret put GOOGLE_API_KEY
npx wrangler secret put CF_AIG_TOKEN
```

Configurar variables (en `wrangler.toml` o dashboard):

- `CF_ACCOUNT_ID`
- `CF_GATEWAY_ID`
- `GEMINI_MODEL` (default `google/gemini-2.5-flash`)

Deploy:

```bash
npm run deploy
```

### 2) Frontend React en Cloudflare Pages

En `frontend` define la URL pública del Worker:

```bash
# frontend/.env.production
VITE_API_BASE=https://email-app-api.<tu-subdominio>.workers.dev
```

Build local:

```bash
cd frontend
npm install
npm run build
```

Deploy con Wrangler Pages:

```bash
npx wrangler pages deploy dist --project-name email-app-frontend
```

### 3) Validación rápida

- `GET https://<worker>/api/health`
- Abrir el frontend en Pages y crear un chat.
- Verificar respuestas de Gemini vía AI Gateway.
