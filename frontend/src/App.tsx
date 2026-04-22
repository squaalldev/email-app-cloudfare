import React, { useEffect, useMemo, useState } from 'react';
import './App.css';
import ChatWindow from './components/ChatWindow';
import ChatHistory from './components/ChatHistory';

export interface ChatSummary {
  chat_id: string;
  title: string;
  updated_at: number;
}

const USER_STORAGE_KEY = 'chatbot_uid';

function getOrCreateUid() {
  const existing = localStorage.getItem(USER_STORAGE_KEY);
  if (existing) return existing;
  const generated = crypto.randomUUID();
  localStorage.setItem(USER_STORAGE_KEY, generated);
  return generated;
}

function App() {
  const uid = useMemo(() => getOrCreateUid(), []);
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [appError, setAppError] = useState<string | null>(null);

  const fetchWithUid = (path: string, init?: RequestInit) => {
    const separator = path.includes('?') ? '&' : '?';
    return fetch(`${path}${separator}uid=${encodeURIComponent(uid)}`, init);
  };

  const getResponseError = async (response: Response, fallback: string) => {
    const body = await response.json().catch(() => null);
    if (body && typeof body.detail === 'string' && body.detail.trim()) {
      return body.detail;
    }
    if (body && typeof body.message === 'string' && body.message.trim()) {
      return body.message;
    }
    return fallback;
  };

  const fetchChats = async () => {
    const response = await fetchWithUid('/api/chats');
    if (!response.ok) {
      const errorMessage = await getResponseError(response, 'No se pudieron cargar los chats');
      setAppError(errorMessage);
      throw new Error(errorMessage);
    }
    const data: ChatSummary[] = await response.json();
    setChats(data);
  };

  useEffect(() => {
    fetchChats().catch(console.error);
  }, []);

  const createChat = async () => {
    const response = await fetchWithUid('/api/chats', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    if (!response.ok) {
      const errorMessage = await getResponseError(response, 'No se pudo crear el chat');
      setAppError(errorMessage);
      throw new Error(errorMessage);
    }

    const created: ChatSummary = await response.json();
    await fetchChats();
    setCurrentChatId(created.chat_id);
    return created.chat_id;
  };

  const ensureChat = async () => {
    if (currentChatId) return currentChatId;
    return createChat();
  };

  return (
    <div className="app-container">
      {appError && (
        <div className="app-error-banner" role="alert">
          <div className="app-error-title">Error</div>
          <div>{appError}</div>
          <button
            className="app-error-close"
            onClick={() => setAppError(null)}
            aria-label="Cerrar mensaje de error"
          >
            ×
          </button>
        </div>
      )}
      <div className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}>
        <button
          className="sidebar-toggle"
          onClick={() => setSidebarCollapsed((prev) => !prev)}
          aria-label={sidebarCollapsed ? 'Mostrar menú de chats' : 'Ocultar menú de chats'}
          title={sidebarCollapsed ? 'Mostrar menú' : 'Ocultar menú'}
        >
          {sidebarCollapsed ? '»' : '«'}
        </button>

        {!sidebarCollapsed && (
          <ChatHistory
            chats={chats}
            currentChatId={currentChatId}
            onSelectChat={setCurrentChatId}
            onNewChat={createChat}
          />
        )}
      </div>
      <div className="main-content">
        <ChatWindow
          chatId={currentChatId}
          uid={uid}
          onRefreshChats={fetchChats}
          onEnsureChat={ensureChat}
          onError={setAppError}
        />
      </div>
    </div>
  );
}

export default App;
