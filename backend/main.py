from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from backend.system_prompts import get_enhanced_prompt, get_unified_email_prompt

load_dotenv()

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
DATA_DIR = Path(os.environ.get("APP_DATA_DIR", "backend/data"))
FRONTEND_DIST = Path("frontend/dist")


class MessageIn(BaseModel):
    content: str = Field(min_length=1)
    is_example: bool = False


class CreateChatIn(BaseModel):
    title: str | None = None


class ChatSummary(BaseModel):
    chat_id: str
    title: str
    updated_at: float


class MessageOut(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatMessageResponse(BaseModel):
    response: str
    chat_id: str


app = FastAPI(title="Chatbot Email API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


def _namespace(request: Request) -> str:
    user_id = request.headers.get("x-user-id") or request.query_params.get("uid") or "default"
    return "".join(ch for ch in user_id if ch.isalnum() or ch in ("-", "_")) or "default"


def _user_dir(namespace: str) -> Path:
    user_dir = DATA_DIR / namespace
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def _index_path(namespace: str) -> Path:
    return _user_dir(namespace) / "chats_index.json"


def _chat_path(namespace: str, chat_id: str) -> Path:
    return _user_dir(namespace) / f"{chat_id}.json"


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_index(namespace: str) -> dict[str, dict]:
    return _read_json(_index_path(namespace), default={})


def _save_index(namespace: str, data: dict[str, dict]) -> None:
    _write_json(_index_path(namespace), data)


def _load_messages(namespace: str, chat_id: str) -> list[dict]:
    payload = _read_json(_chat_path(namespace, chat_id), default={"messages": []})
    return payload.get("messages", [])


def _save_messages(namespace: str, chat_id: str, messages: list[dict]) -> None:
    _write_json(_chat_path(namespace, chat_id), {"messages": messages})


def _title_from_prompt(prompt: str) -> str:
    cleaned = re.sub(r"\s+", " ", (prompt or "").strip())
    cleaned = re.sub(r"[\n\r\t]+", " ", cleaned)
    cleaned = re.sub(r"[^\w\sáéíóúÁÉÍÓÚñÑüÜ¿?¡!,:.-]", "", cleaned)
    words = cleaned.split()
    if not words:
        return f"Sesión-{int(time.time())}"
    return " ".join(words[:7])


def _generate_title(client: genai.Client, prompt: str) -> str:
    try:
        result = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=(
                "Genera un título natural y humano en español (3 a 6 palabras) "
                "que resuma esta consulta. Devuelve solo el título final: "
                f"'{prompt}'"
            ),
        )
        title = " ".join((result.text or "").strip().replace('"', "").split())
        candidate = " ".join(title.split()[:6])
        return candidate or _title_from_prompt(prompt)
    except Exception:
        return _title_from_prompt(prompt)




def _initialize_model(api_key: str | None = None) -> genai.Client:
    resolved_api_key = api_key or GOOGLE_API_KEY
    if not resolved_api_key:
        raise HTTPException(
            status_code=500,
            detail=(
                "GOOGLE_API_KEY no está configurada. En Hugging Face Spaces agrega este valor en Settings > Secrets."
            ),
        )

    try:
        return genai.Client(api_key=resolved_api_key)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo inicializar Gemini con GOOGLE_API_KEY: {exc}",
        ) from exc

def _build_contents(messages: list[dict]) -> list[types.Content]:
    contents: list[types.Content] = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
    return contents


@app.get("/api/health")
def health_check():
    return {"ok": True}


@app.get("/api/chats", response_model=list[ChatSummary])
def list_chats(request: Request):
    index = _load_index(_namespace(request))
    rows = [
        ChatSummary(chat_id=chat_id, title=row["title"], updated_at=row.get("updated_at", 0.0))
        for chat_id, row in index.items()
    ]
    return sorted(rows, key=lambda row: row.updated_at, reverse=True)


@app.post("/api/chats", response_model=ChatSummary)
def create_chat(payload: CreateChatIn, request: Request):
    namespace = _namespace(request)
    chat_id = str(int(time.time() * 1000)) + uuid.uuid4().hex[:6]
    index = _load_index(namespace)
    now = time.time()
    title = payload.title or "Nuevo chat"
    index[chat_id] = {"title": title, "updated_at": now}
    _save_index(namespace, index)
    _save_messages(namespace, chat_id, [])
    return ChatSummary(chat_id=chat_id, title=title, updated_at=now)


@app.get("/api/chats/{chat_id}/messages", response_model=list[MessageOut])
def get_messages(chat_id: str, request: Request):
    namespace = _namespace(request)
    index = _load_index(namespace)
    if chat_id not in index:
        raise HTTPException(status_code=404, detail="Chat no encontrado")
    messages = _load_messages(namespace, chat_id)
    return [MessageOut(role=m["role"], content=m["content"]) for m in messages]


@app.post("/api/chats/{chat_id}/messages", response_model=ChatMessageResponse)
def send_message(chat_id: str, payload: MessageIn, request: Request):
    namespace = _namespace(request)
    index = _load_index(namespace)
    if chat_id not in index:
        raise HTTPException(status_code=404, detail="Chat no encontrado")

    messages = _load_messages(namespace, chat_id)
    user_message = {"role": "user", "content": payload.content}
    messages.append(user_message)

    client = _initialize_model()
    first_user_message = len([m for m in messages if m["role"] == "user"]) == 1
    enhanced_prompt = get_enhanced_prompt(
        payload.content,
        is_example=payload.is_example,
        is_first_user_message=first_user_message,
    )

    messages_for_model = messages[:-1] + [{"role": "user", "content": enhanced_prompt}]

    response = client.models.generate_content(
        model=DEFAULT_MODEL,
        contents=_build_contents(messages_for_model),
        config=types.GenerateContentConfig(system_instruction=get_unified_email_prompt()),
    )

    assistant_text = (response.text or "").strip()
    if not assistant_text:
        assistant_text = "No pude generar respuesta en este intento."

    messages.append({"role": "assistant", "content": assistant_text})
    _save_messages(namespace, chat_id, messages)

    current_title = (index[chat_id].get("title") or "").strip().lower()
    if not current_title or current_title.startswith("sesión-") or current_title == "nuevo chat":
        index[chat_id]["title"] = _generate_title(client, payload.content)
    index[chat_id]["updated_at"] = time.time()
    _save_index(namespace, index)

    return ChatMessageResponse(response=assistant_text, chat_id=chat_id)


# Backward compatibility for previous React call
@app.post("/api/chat/send", response_model=ChatMessageResponse)
def send_message_legacy(payload: MessageIn, request: Request):
    namespace = _namespace(request)
    index = _load_index(namespace)
    if not index:
        chat = create_chat(CreateChatIn(title="Nuevo chat"), request)
    else:
        latest_chat = sorted(index.items(), key=lambda item: item[1].get("updated_at", 0), reverse=True)[0]
        chat = ChatSummary(chat_id=latest_chat[0], title=latest_chat[1]["title"], updated_at=latest_chat[1]["updated_at"])
    return send_message(chat.chat_id, payload, request)


@app.get("/{full_path:path}")
def serve_react_app(full_path: str):
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "message": "API running. Frontend build not found.",
        "hint": "Build frontend with: cd frontend && npm run build",
    }
