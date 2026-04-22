interface Env {
  CHAT_KV: KVNamespace;
  CF_ACCOUNT_ID: string;
  CF_GATEWAY_ID: string;
  CF_AIG_TOKEN?: string;
  GOOGLE_API_KEY: string;
  GEMINI_MODEL?: string;
}

type Role = 'user' | 'assistant';
interface ChatSummary { chat_id: string; title: string; updated_at: number }
interface ChatMessage { role: Role; content: string }

const corsHeaders = {
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET,POST,OPTIONS',
  'access-control-allow-headers': 'Content-Type',
};

const json = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', ...corsHeaders },
  });

const normalizeUid = (uid: string | null) => {
  const fallback = 'default';
  if (!uid) return fallback;
  const cleaned = uid.replace(/[^a-zA-Z0-9_-]/g, '');
  return cleaned || fallback;
};

const indexKey = (uid: string) => `u:${uid}:index`;
const chatKey = (uid: string, chatId: string) => `u:${uid}:chat:${chatId}`;

const loadIndex = async (env: Env, uid: string): Promise<Record<string, ChatSummary>> => {
  return (await env.CHAT_KV.get(indexKey(uid), 'json')) || {};
};

const saveIndex = async (env: Env, uid: string, data: Record<string, ChatSummary>) => {
  await env.CHAT_KV.put(indexKey(uid), JSON.stringify(data));
};

const loadMessages = async (env: Env, uid: string, chatId: string): Promise<ChatMessage[]> => {
  const payload = await env.CHAT_KV.get(chatKey(uid, chatId), 'json');
  return (payload as { messages?: ChatMessage[] } | null)?.messages || [];
};

const saveMessages = async (env: Env, uid: string, chatId: string, messages: ChatMessage[]) => {
  await env.CHAT_KV.put(chatKey(uid, chatId), JSON.stringify({ messages }));
};

const gatewayUrl = (env: Env) =>
  `https://gateway.ai.cloudflare.com/v1/${env.CF_ACCOUNT_ID}/${env.CF_GATEWAY_ID}/compat/chat/completions`;

const generateReply = async (env: Env, messages: ChatMessage[]) => {
  const model = env.GEMINI_MODEL || 'google/gemini-2.5-flash';
  const resp = await fetch(gatewayUrl(env), {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      authorization: `Bearer ${env.GOOGLE_API_KEY}`,
      ...(env.CF_AIG_TOKEN ? { 'cf-aig-authorization': `Bearer ${env.CF_AIG_TOKEN}` } : {}),
    },
    body: JSON.stringify({
      model,
      messages: messages.map((m) => ({ role: m.role === 'assistant' ? 'assistant' : 'user', content: m.content })),
      temperature: 0.7,
    }),
  });

  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`AI Gateway error (${resp.status}): ${body}`);
  }

  const data = (await resp.json()) as {
    choices?: Array<{ message?: { content?: string } }>;
  };
  return data.choices?.[0]?.message?.content?.trim() || 'No pude generar respuesta en este intento.';
};

const createChat = async (env: Env, uid: string, title = 'Nuevo chat') => {
  const now = Date.now();
  const chat_id = `${now}-${crypto.randomUUID().slice(0, 6)}`;
  const index = await loadIndex(env, uid);
  index[chat_id] = { chat_id, title, updated_at: now / 1000 };
  await saveIndex(env, uid, index);
  await saveMessages(env, uid, chat_id, []);
  return index[chat_id];
};

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === 'OPTIONS') return new Response(null, { headers: corsHeaders });

    const url = new URL(request.url);
    const uid = normalizeUid(url.searchParams.get('uid'));

    try {
      if (url.pathname === '/api/health' && request.method === 'GET') return json({ ok: true });

      if (url.pathname === '/api/chats' && request.method === 'GET') {
        const index = await loadIndex(env, uid);
        const chats = Object.values(index).sort((a, b) => b.updated_at - a.updated_at);
        return json(chats);
      }

      if (url.pathname === '/api/chats' && request.method === 'POST') {
        const payload = (await request.json().catch(() => ({}))) as { title?: string };
        const chat = await createChat(env, uid, payload.title || 'Nuevo chat');
        return json(chat, 201);
      }

      const msgMatch = url.pathname.match(/^\/api\/chats\/([^/]+)\/messages$/);
      if (msgMatch && request.method === 'GET') {
        const chatId = msgMatch[1];
        const messages = await loadMessages(env, uid, chatId);
        return json(messages);
      }

      if (msgMatch && request.method === 'POST') {
        const chatId = msgMatch[1];
        const payload = (await request.json()) as { content?: string };
        if (!payload.content?.trim()) return json({ detail: 'content es requerido' }, 400);

        const index = await loadIndex(env, uid);
        if (!index[chatId]) return json({ detail: 'Chat no encontrado' }, 404);

        const messages = await loadMessages(env, uid, chatId);
        messages.push({ role: 'user', content: payload.content });
        const reply = await generateReply(env, messages);
        messages.push({ role: 'assistant', content: reply });
        await saveMessages(env, uid, chatId, messages);

        index[chatId].updated_at = Date.now() / 1000;
        await saveIndex(env, uid, index);

        return json({ response: reply, chat_id: chatId });
      }

      if (url.pathname === '/api/chat/send' && request.method === 'POST') {
        const payload = (await request.json()) as { content?: string };
        if (!payload.content?.trim()) return json({ detail: 'content es requerido' }, 400);

        const index = await loadIndex(env, uid);
        const latest = Object.values(index).sort((a, b) => b.updated_at - a.updated_at)[0];
        const chat = latest || (await createChat(env, uid));

        const messages = await loadMessages(env, uid, chat.chat_id);
        messages.push({ role: 'user', content: payload.content });
        const reply = await generateReply(env, messages);
        messages.push({ role: 'assistant', content: reply });
        await saveMessages(env, uid, chat.chat_id, messages);

        return json({ response: reply, chat_id: chat.chat_id });
      }

      return json({ detail: 'Not found' }, 404);
    } catch (error) {
      const detail = error instanceof Error ? error.message : 'Unknown error';
      return json({ detail }, 500);
    }
  },
};
