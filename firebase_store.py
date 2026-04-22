import os
import json
from typing import Optional

import streamlit as st

try:
    import firebase_admin
    from firebase_admin import auth, credentials, firestore
except Exception:  # pragma: no cover - entorno sin dependencia
    firebase_admin = None
    auth = None
    credentials = None
    firestore = None


class FirebaseSessionStore:
    """Persistencia de sesiones en Firebase (Fase 1 rápida)."""

    def __init__(self, db):
        self.db = db

    @classmethod
    def from_env(cls) -> Optional["FirebaseSessionStore"]:
        if firebase_admin is None:
            return None

        service_account_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
        service_account_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
        if not service_account_json and not service_account_path:
            return None

        if not firebase_admin._apps:
            if service_account_json:
                cred_info = json.loads(service_account_json)
                cred = credentials.Certificate(cred_info)
            else:
                cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)

        return cls(firestore.client())

    def verify_id_token(self, id_token: str) -> Optional[str]:
        if not id_token:
            return None
        try:
            decoded = auth.verify_id_token(id_token)
            return decoded.get("uid")
        except Exception as exc:
            st.warning(f"No se pudo validar token Firebase: {exc}")
            return None

    def _index_ref(self, user_id: str):
        return self.db.collection("users").document(user_id).collection("meta").document("chat_index")

    def _history_ref(self, user_id: str, chat_id: str):
        return self.db.collection("users").document(user_id).collection("chats").document(str(chat_id))

    def load_chat_index(self, user_id: str) -> dict:
        doc = self._index_ref(user_id).get()
        if not doc.exists:
            return {}
        return doc.to_dict().get("past_chats", {})

    def save_chat_index(self, user_id: str, past_chats: dict) -> None:
        self._index_ref(user_id).set({"past_chats": past_chats}, merge=True)

    def save_chat_history(self, user_id: str, chat_id: str, messages: list, gemini_history: list) -> None:
        self._history_ref(user_id, chat_id).set(
            {
                "messages": messages,
                "gemini_history": gemini_history,
            },
            merge=True,
        )

    def load_chat_history(self, user_id: str, chat_id: str):
        doc = self._history_ref(user_id, chat_id).get()
        if not doc.exists:
            return None, None
        data = doc.to_dict() or {}
        return data.get("messages"), data.get("gemini_history")
