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
