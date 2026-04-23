# Integración de Cloudflare + Gemini en este proyecto (React + FastAPI)

Esta guía está pensada para **este repo** (frontend React + backend FastAPI) y para usar Gemini de forma segura con Cloudflare.

## Resumen rápido de arquitectura

Para un proyecto React, la opción más segura es:

1. **React** llama a tu **backend FastAPI** (nunca directo a Gemini con API key en el navegador).
2. FastAPI llama a **Cloudflare AI Gateway**.
3. AI Gateway enruta a **Google AI Studio (Gemini)**.

> Workers AI y AI Gateway no son lo mismo:
> - **Workers AI**: modelos hosteados por Cloudflare.
> - **AI Gateway**: proxy/observabilidad/rate-limit para proveedores externos (incluye Gemini).

## Lo importante de la doc de Cloudflare

Según la documentación oficial:

- Workers AI expone endpoint compatible OpenAI (`/v1/chat/completions`, `/v1/embeddings`) para modelos de Workers AI.
- AI Gateway ofrece dos formas:
  - Endpoint **compat** (estilo OpenAI):
    - `https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}/compat`
  - Endpoint **provider-specific**:
    - `https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}/{provider}`
- Para Gemini, Cloudflare muestra el provider `google-ai-studio`.

## Opción recomendada para tu app actual

Como ya usas Gemini (`google-genai`) en backend Python, migra ese tráfico a **AI Gateway** en vez de llamar directo a Google.

### Variables de entorno sugeridas

En backend agrega:

- `CF_ACCOUNT_ID`
- `CF_GATEWAY_ID`
- `CF_AIG_TOKEN` (token del gateway autenticado)
- `GOOGLE_API_KEY` (si usas clave en request) **o** configuración BYOK en AI Gateway
- `GEMINI_MODEL` (ej. `gemini-2.5-flash`)

## Patrón de llamada (sin exponer secretos al frontend)

### A) Provider-specific (Gemini nativo)

URL base:

`https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}/google-ai-studio`

Luego llamas la ruta de Gemini (por ejemplo `.../v1/models/{model}:generateContent`) con:

- `x-goog-api-key: <GOOGLE_API_KEY>`
- y opcionalmente `cf-aig-authorization: Bearer <CF_AIG_TOKEN>`

### B) Compat endpoint (estilo OpenAI)

URL base:

`https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}/compat`

Modelo ejemplo:

`google/gemini-2.5-pro`

Este modo sirve si quieres unificar proveedores con SDK OpenAI-compatible.

## ¿Dónde entra Workers AI aquí?

Si después quieres fallback barato o modelos open-source, puedes rutear por AI Gateway también hacia Workers AI con modelos tipo:

`workers-ai/@cf/meta/llama-3.3-70b-instruct-fp8-fast`

Así tendrás una sola capa de observabilidad/rate-limit/fallback en Cloudflare.

## Checklist de implementación en este repo

1. Crear AI Gateway en tu cuenta Cloudflare.
2. Definir política de autenticación (`cf-aig-authorization`) y rate limits.
3. Ajustar backend FastAPI para usar URL de AI Gateway (no exponer llaves en React).
4. Mantener React igual: seguir pegándole a `/api/...`.
5. Probar trazas y métricas en el dashboard de AI Gateway.

## Buenas prácticas

- Nunca pongas `GOOGLE_API_KEY` en `frontend/.env`.
- Mantén CORS restringido en producción (no `*`).
- Agrega timeout/retries del lado backend.
- Activa caching/fallback en AI Gateway para resiliencia y costo.

## Enlaces oficiales

- Workers AI Overview: https://developers.cloudflare.com/workers-ai/
- Workers AI OpenAI-compatible: https://developers.cloudflare.com/workers-ai/configuration/open-ai-compatibility/
- AI Gateway Get started: https://developers.cloudflare.com/ai-gateway/get-started/
- AI Gateway Google AI Studio (Gemini): https://developers.cloudflare.com/ai-gateway/usage/providers/google-ai-studio/


## Deploy real en Cloudflare para este repo

### Backend (Workers)

Se añadió un Worker listo en `cloudflare/worker-api`.

```bash
cd cloudflare/worker-api
npm install
npx wrangler kv namespace create CHAT_KV
# pega el ID en wrangler.toml
npx wrangler secret put GOOGLE_API_KEY
npx wrangler secret put CF_AIG_TOKEN
npm run deploy
```

### Frontend (Pages)

```bash
cd frontend
npm install
npm run build
npx wrangler pages deploy dist --project-name email-app-frontend
```

Conecta frontend -> backend con:

```bash
# frontend/.env.production
VITE_API_BASE=https://email-app-api.<tu-subdominio>.workers.dev
```


## Cómo cargar secrets (rápido)

En `cloudflare/worker-api`:

```bash
npx wrangler secret put GOOGLE_API_KEY
npx wrangler secret put CF_AIG_TOKEN
npx wrangler secret list
```

Con environment específico:

```bash
npx wrangler secret put GOOGLE_API_KEY --env production
npx wrangler secret put CF_AIG_TOKEN --env production
```

En dashboard: **Workers & Pages → tu Worker → Settings → Variables and Secrets → Secrets**.


## Troubleshooting: "only has static assets"

Si en Settings ves: **"Variables cannot be added to a Worker that only has static assets"**, no es un Worker de runtime, es un despliegue estático.

Debes desplegar el backend desde `cloudflare/worker-api` (con `main = "src/index.ts"` en `wrangler.toml`) para habilitar secrets/bindings.

Checklist rápido:
- Root directory del proyecto Worker: `cloudflare/worker-api`
- Deploy command: `npm run deploy` o `npx wrangler deploy`
- Confirmar que en runtime exista handler `fetch` (archivo `src/index.ts`)
- Re-deploy
