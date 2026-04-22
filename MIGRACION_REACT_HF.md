# Plan de migración: lógica Python (Streamlit) → React moderno + backend compatible con Hugging Face Spaces

## 1) Hallazgos de la revisión actual

### Backend Python existente
- `app.py` contiene prácticamente toda la lógica de producto: manejo de sesiones, títulos de chat, menú inicial, prompts de ejemplo y streaming de respuesta desde Gemini. Está fuertemente acoplado a Streamlit (`st.session_state`, `st.chat_message`, `st.chat_input`, `st.rerun`).
- `session_state.py` implementa persistencia local por usuario (`data/<namespace>`) y encapsula llamadas a `google-genai` con `send_message_stream`.
- `system_prompts.py` define el prompt maestro del flujo de 5 preguntas y formato final del email.
- `firebase_store.py` ya anticipa un backend con persistencia remota (Firestore) para índice/historial de chats.

### Frontend React existente
- Ya hay estructura Vite + React + TypeScript.
- `ChatWindow.tsx` consume `POST /api/chat/send`, pero ese endpoint no existe en `backend/main.py`.
- `ChatWindow.tsx` actualmente reinicia mensajes al cambiar chat y no carga historial desde servidor.
- `ChatHistory.tsx` y `App.tsx` mantienen datos en memoria local del navegador, sin sincronización real.

### Desalineaciones de infraestructura
- `backend/main.py` solo monta archivos estáticos y no expone API funcional.
- `backend/gemini_service.py` usa un endpoint no estándar de Gemini (`https://gemini.googleapis.com/v1/email/generate`) y no coincide con el SDK usado en `session_state.py`.
- `Dockerfile` espera `frontend/build`, pero Vite genera `dist`.

## 2) Objetivo técnico recomendado

Separar la app en capas limpias:
1. **Frontend React (UI + estado de vista)**
2. **Backend FastAPI (lógica de negocio + Gemini + persistencia)**
3. **Proveedor de almacenamiento** (local JSON/SQLite para MVP y Firebase opcional)

Esto te deja una base escalable para HF Spaces (Docker SDK) y para crecer a multiusuario real.

## 3) Qué lógica debes mover de Python a React y cuál NO

### Mover a React (presentación y UX)
- Render de chat (mensajes, indicador "escribiendo", input).
- Menú inicial y botones de ejemplos.
- Sidebar de sesiones y navegación entre chats.
- Estado visual (loading, error, disabled states).

### Mantener en backend (dominio y seguridad)
- Lógica de `get_enhanced_prompt` (saludo y modo ejemplo).
- Generación de título de chat por IA.
- Integración con Gemini y streaming.
- Persistencia de historiales por usuario/chat.
- Reglas de negocio del flujo guiado.

> Regla práctica: si algo implica API keys, reglas de negocio o consistencia de datos, va en backend.

## 4) Arquitectura de API sugerida (contratos)

### Endpoints mínimos
- `POST /api/chats` → crea chat y devuelve `{chat_id, title}`
- `GET /api/chats` → lista chats del usuario
- `GET /api/chats/{chat_id}/messages` → historial
- `POST /api/chats/{chat_id}/messages` → agrega mensaje y devuelve respuesta IA
- `GET /api/prompts/examples` → ejemplos iniciales (opcional, para no hardcodear)

### Streaming recomendado
Para una UX moderna:
- Preferir **SSE** (`text/event-stream`) o **chunked responses** para tokens.
- Frontend consume stream y va pintando texto incrementalmente.

## 5) Plan de implementación por fases

### Fase 0 — Alineación de base
1. Consolidar `system_prompts.py` en backend y eliminar duplicados.
2. Definir modelos Pydantic (`Chat`, `Message`, `SendMessageRequest`, `SendMessageResponse`).
3. Corregir `backend/requirements.txt` para usar `google-genai`.

### Fase 1 — Backend funcional
1. Crear `backend/services/chat_service.py` con:
   - `create_chat`
   - `list_chats`
   - `send_message`
   - `load_history`
2. Crear `backend/repositories` con interfaz de persistencia:
   - `local_repo.py` (MVP)
   - `firebase_repo.py` (adaptando `firebase_store.py`)
3. Implementar rutas en `backend/main.py` para `/api/*`.

### Fase 2 — Frontend robusto
1. Crear capa de cliente API en `frontend/src/lib/api.ts`.
2. Introducir estado global con **TanStack Query** + store liviano (Zustand o Context).
3. Refactor de componentes:
   - `ChatShell` (layout)
   - `ChatSidebar`
   - `MessageList`
   - `Composer`
4. Manejar errores con toasts y estados vacíos.

### Fase 3 — Hugging Face Spaces
1. Ajustar `Dockerfile` multi-stage:
   - Stage Node: build de Vite (`dist`)
   - Stage Python: FastAPI + copiar `dist` a carpeta estática
2. FastAPI debe servir estáticos y fallback SPA (`index.html`).
3. Variables HF:
   - `GOOGLE_API_KEY`
   - opcional: `FIREBASE_SERVICE_ACCOUNT_JSON`

### Fase 4 — Escalabilidad
1. Añadir auth (al menos token por usuario o Firebase Auth).
2. Trazas/observabilidad (logs estructurados + request_id).
3. Tests:
   - unit tests de servicio
   - contract tests de API
   - e2e básico de chat

## 6) Decisiones técnicas concretas recomendadas

- **Gemini**: usar solo `google-genai` (evitar `requests` custom mientras no sea imprescindible).
- **Persistencia**: iniciar con SQLite o JSON por simplicidad; dejar interfaz para Firebase.
- **Estado frontend**:
  - Server state: TanStack Query
  - UI state: Zustand/Context
- **Tipado**: compartir esquemas con OpenAPI generado por FastAPI + tipos TS (openapi-typescript).

## 7) Riesgos actuales que debes corregir primero

1. Endpoint `/api/chat/send` inexistente (rompe el frontend actual).
2. `Dockerfile` incompatible con salida Vite (`dist` vs `build`).
3. Doble fuente de verdad (Streamlit app y React app conviviendo sin contratos unificados).
4. Persistencia local por archivos (`joblib`) no ideal para multiinstancia.

## 8) Backlog accionable (orden sugerido)

1. Implementar API real en `backend/main.py`.
2. Conectar `ChatWindow.tsx` a nueva API de chats/mensajes.
3. Reemplazar estado local de chats en `App.tsx` por datos del backend.
4. Migrar streaming al frontend con SSE.
5. Ajustar Docker para HF y probar build end-to-end.

## 9) Criterios de “migración completada”

- La UI React reproduce toda la UX importante de Streamlit (menu inicial, ejemplos, historial, multi-chat).
- Toda llamada a Gemini pasa por FastAPI (ninguna key en frontend).
- Persistencia de chats disponible al recargar.
- Docker build exitoso y despliegue en HF Space operativo.

---

Si quieres, en la siguiente iteración puedo convertir este plan en tareas técnicas concretas por archivo (`backend/main.py`, `frontend/src/components/*`, `Dockerfile`) y proponerte un PR incremental fase por fase.
