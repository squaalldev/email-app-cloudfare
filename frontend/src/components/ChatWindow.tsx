import React, { useEffect, useMemo, useState } from 'react';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'error';
  content: string;
  avatar: string;
}

interface ApiMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface Props {
  chatId: string | null;
  uid: string;
  onRefreshChats: () => Promise<void>;
  onEnsureChat: () => Promise<string>;
  onError: (error: string | null) => void;
}

interface ExamplePrompt {
  label: string;
  prompt: string;
}

const EXAMPLE_PROMPTS: ExamplePrompt[] = [
  {
    label: 'Definir audiencia 🎯',
    prompt: 'Ayúdame a definir una audiencia concreta para este correo: dolor principal, deseo y nivel de conciencia.',
  },
  {
    label: 'Propuesta de valor 💎',
    prompt: 'Convierte mi producto en una promesa clara de transformación sin listar características aburridas.',
  },
  {
    label: 'CTA que convierte 🚀',
    prompt: 'Dame 3 opciones de CTA claras para este email, con baja fricción y orientadas a una sola acción.',
  },
  {
    label: 'Asunto + gancho ✉️',
    prompt: 'Propón 5 asuntos y 3 ganchos de apertura para aumentar aperturas y clics de este correo.',
  },
];

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const escapeHtml = (text: string) =>
  text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

const inlineMarkdown = (text: string) => {
  let html = escapeHtml(text);
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  return html;
};

const markdownToHtml = (raw: string) => {
  const lines = raw.split('\n');
  const output: string[] = [];
  let inUl = false;
  let inOl = false;

  const closeLists = () => {
    if (inUl) {
      output.push('</ul>');
      inUl = false;
    }
    if (inOl) {
      output.push('</ol>');
      inOl = false;
    }
  };

  lines.forEach((line) => {
    const trimmed = line.trim();

    if (!trimmed) {
      closeLists();
      output.push('<br />');
      return;
    }

    if (trimmed.startsWith('### ')) {
      closeLists();
      output.push(`<h3>${inlineMarkdown(trimmed.slice(4))}</h3>`);
      return;
    }

    if (trimmed.startsWith('## ')) {
      closeLists();
      output.push(`<h2>${inlineMarkdown(trimmed.slice(3))}</h2>`);
      return;
    }

    if (trimmed.startsWith('# ')) {
      closeLists();
      output.push(`<h1>${inlineMarkdown(trimmed.slice(2))}</h1>`);
      return;
    }

    const ordered = trimmed.match(/^(\d+)\.\s+(.*)$/);
    if (ordered) {
      if (inUl) {
        output.push('</ul>');
        inUl = false;
      }
      if (!inOl) {
        output.push('<ol>');
        inOl = true;
      }
      output.push(`<li>${inlineMarkdown(ordered[2])}</li>`);
      return;
    }

    const bullet = trimmed.match(/^[-*]\s+(.*)$/);
    if (bullet) {
      if (inOl) {
        output.push('</ol>');
        inOl = false;
      }
      if (!inUl) {
        output.push('<ul>');
        inUl = true;
      }
      output.push(`<li>${inlineMarkdown(bullet[1])}</li>`);
      return;
    }

    closeLists();
    output.push(`<p>${inlineMarkdown(trimmed)}</p>`);
  });

  closeLists();
  return output.join('');
};

const withUidPath = (path: string, uid: string) =>
  `${path}${path.includes('?') ? '&' : '?'}uid=${encodeURIComponent(uid)}`;

function toUiMessage(msg: ApiMessage, idx: number): Message {
  return {
    id: `${msg.role}-${idx}-${Date.now()}`,
    role: msg.role,
    content: msg.content,
    avatar: msg.role === 'user' ? '👤' : '🤖',
  };
}

function ChatWindow({ chatId, uid, onRefreshChats, onEnsureChat, onError }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [feedbackByMessage, setFeedbackByMessage] = useState<Record<string, 'up' | 'down'>>({});
  const [chatError, setChatError] = useState<string | null>(null);

  const loadMessages = async (targetChatId: string) => {
    const response = await fetch(withUidPath(`/api/chats/${targetChatId}/messages`, uid));
    if (!response.ok) {
      throw new Error('No se pudo cargar el historial');
    }

    const data: ApiMessage[] = await response.json();
    setMessages(data.map((msg, idx) => toUiMessage(msg, idx)));
  };

  useEffect(() => {
    if (!chatId || loading) return;

    loadMessages(chatId).catch((error) => {
      const message = error instanceof Error ? error.message : 'No se pudo cargar el historial';
      setChatError(message);
      onError(message);
    });
  }, [chatId, loading, onError]);

  const animateAssistantText = async (messageId: string, fullText: string) => {
    let partial = '';
    for (const char of fullText) {
      partial += char;
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === messageId
            ? {
                ...msg,
                content: partial,
              }
            : msg,
        ),
      );
      await sleep(8);
    }
  };

  const sendToCurrentChat = async (content: string, isExample = false) => {
    const activeChatId = await onEnsureChat();

    const userMessage: Message = {
      id: `${Date.now()}-user`,
      role: 'user',
      content,
      avatar: '👤',
    };

    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);
    setChatError(null);

    try {
      const response = await fetch(withUidPath(`/api/chats/${activeChatId}/messages`, uid), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, is_example: isExample }),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || 'Error enviando mensaje');
      }

      const data = await response.json();
      const assistantId = `${Date.now()}-assistant`;
      const assistantMessage: Message = {
        id: assistantId,
        role: 'assistant',
        content: '',
        avatar: '🤖',
      };

      setMessages((prev) => [...prev, assistantMessage]);
      await animateAssistantText(assistantId, data.response ?? '');
      await onRefreshChats();
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Error enviando mensaje';
      setChatError(msg);
      onError(msg);
      setMessages((prev) => [
        ...prev,
        {
          id: `${Date.now()}-error`,
          role: 'error',
          content: msg,
          avatar: '⚠️',
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const hasInput = input.trim().length > 0;

  const handleSendMessage = async () => {
    if (!input.trim() || loading) return;
    const content = input;
    setInput('');
    await sendToCurrentChat(content, false);
  };

  const dismissChatError = () => {
    setChatError(null);
    onError(null);
  };

  const assistantHtmlById = useMemo(() => {
    const map = new Map<string, string>();
    messages.forEach((message) => {
      if (message.role === 'assistant') {
        map.set(message.id, markdownToHtml(message.content));
      }
    });
    return map;
  }, [messages]);

  const handleCopy = async (messageId: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setFeedbackByMessage((prev) => ({ ...prev, [messageId]: prev[messageId] || 'up' }));
    } catch (error) {
      console.error('No se pudo copiar:', error);
    }
  };

  const handleFeedback = (messageId: string, type: 'up' | 'down') => {
    setFeedbackByMessage((prev) => {
      const current = prev[messageId];
      if (current === type) {
        const next = { ...prev };
        delete next[messageId];
        return next;
      }
      return { ...prev, [messageId]: type };
    });
  };

  return (
    <div className="chat-window">
      <div className="messages">
        {chatError && (
          <div className="chat-error-banner" role="alert">
            <strong>Error:</strong> {chatError}
            <button
              className="chat-error-close"
              onClick={dismissChatError}
              aria-label="Cerrar error del chat"
            >
              ×
            </button>
          </div>
        )}
        {messages.length === 0 && (
          <div className="initial-menu">
            <img
              className="brand-remote-logo"
              src="https://huggingface.co/spaces/JeCabrera/chatbot_mail/resolve/main/robocopy_logo.png"
              alt="RoboCopy"
            />
            <h1 className="robocopy-title">Email Story Creator</h1>
            <span className="brand-author subtitle">By Jesús Cabrera</span>
            <p>✉️ Experto en emails narrativos que conectan historias con ventas de forma natural</p>
            <div className="example-buttons">
              {EXAMPLE_PROMPTS.map((example) => (
                <button
                  key={example.label}
                  className="example-btn"
                  onClick={() => sendToCurrentChat(example.prompt, true)}
                >
                  {example.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`message ${msg.role}`}>
            <span className="avatar">{msg.avatar}</span>
            <div className="content">
              {msg.role === 'assistant' ? (
                <>
                  <div
                    className="assistant-markdown"
                    dangerouslySetInnerHTML={{ __html: assistantHtmlById.get(msg.id) || '' }}
                  />
                  <div className="assistant-actions">
                    <button
                      className="action-btn"
                      onClick={() => handleCopy(msg.id, msg.content)}
                      aria-label="Copiar respuesta"
                      title="Copiar"
                    >
                      ⧉
                    </button>
                    <button
                      className={`action-btn ${feedbackByMessage[msg.id] === 'up' ? 'active' : ''}`}
                      onClick={() => handleFeedback(msg.id, 'up')}
                      aria-label="Respuesta útil"
                      title="Bien"
                    >
                      👍
                    </button>
                    <button
                      className={`action-btn ${feedbackByMessage[msg.id] === 'down' ? 'active' : ''}`}
                      onClick={() => handleFeedback(msg.id, 'down')}
                      aria-label="Respuesta no útil"
                      title="Mal"
                    >
                      👎
                    </button>
                  </div>
                </>
              ) : (
                <div className={msg.role === 'error' ? 'error-plain' : 'user-plain'}>{msg.content}</div>
              )}
            </div>
          </div>
        ))}

        {loading && <div className="message loading">🤖 Escribiendo...</div>}
      </div>

      <div className="input-area">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
          placeholder="Escribe aquí tus instrucciones"
        />
        {hasInput && <span className="input-ready" aria-hidden="true">✓</span>}
        <button
          className={`send-btn ${hasInput ? 'active' : ''}`}
          onClick={handleSendMessage}
          aria-label="Enviar mensaje"
        >
          ↑
        </button>
      </div>
    </div>
  );
}

export default ChatWindow;
