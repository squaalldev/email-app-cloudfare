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



### 1.1) ¿Cómo meto los secrets en Cloudflare?

Tienes 2 opciones:

#### Opción A: CLI (recomendada)
Desde `cloudflare/worker-api`:

```bash
npx wrangler secret put GOOGLE_API_KEY
npx wrangler secret put CF_AIG_TOKEN
```

Wrangler te pedirá el valor de cada secret en stdin y lo guarda cifrado en Cloudflare.

Si usas ambientes:

```bash
npx wrangler secret put GOOGLE_API_KEY --env production
npx wrangler secret put CF_AIG_TOKEN --env production
```

Listar nombres de secrets (sin mostrar valores):

```bash
npx wrangler secret list
```

#### Opción B: Dashboard Cloudflare
1. Ve a **Workers & Pages**.
2. Abre tu Worker `email-app-api`.
3. Entra a **Settings → Variables and Secrets**.
4. En **Secrets**, agrega:
   - `GOOGLE_API_KEY`
   - `CF_AIG_TOKEN` (opcional)
5. Guarda y vuelve a desplegar si es necesario.

> Nota: `CF_ACCOUNT_ID` y `CF_GATEWAY_ID` pueden ir en `[vars]` de `wrangler.toml` (no secretos), pero también puedes manejarlos como secrets si prefieres.


### 1.2) Si no te deja agregar secrets (caso de tu screenshot)

Si ves el mensaje **"Variables cannot be added to a Worker that only has static assets"**, ese Worker fue creado como **Static Assets only** (sin runtime handler).

Eso pasa cuando Cloudflare está subiendo solo archivos estáticos y no está usando `main = "src/index.ts"`.

**Cómo corregirlo:**

1. En Cloudflare, crea (o ajusta) un Worker de API que apunte al proyecto `cloudflare/worker-api`.
2. En Build settings del Worker, usa:
   - **Root directory**: `cloudflare/worker-api`
   - **Deploy command**: `npm run deploy` (o `npx wrangler deploy`)
3. Verifica que el `wrangler.toml` cargado sea el de `cloudflare/worker-api` (debe tener `main = "src/index.ts"`).
4. Vuelve a desplegar.
5. Después de eso, ya aparecerá habilitada la sección de **Variables and Secrets** para agregar `GOOGLE_API_KEY` y `CF_AIG_TOKEN`.

> Recomendación: separa frontend y backend en dos proyectos:
> - `email-app-frontend` (Pages)
> - `email-app-api` (Worker runtime)

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
