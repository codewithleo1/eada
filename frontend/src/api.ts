import axios from "axios";

const API_BASE = "http://localhost:8000";

export const api = axios.create({
  baseURL: API_BASE,
});

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  role: string;
  content: string;
  created_at: string;
}

export interface ConversationDetail extends ConversationSummary {
  messages: Message[];
}

export async function register(
  username: string,
  password: string
): Promise<TokenResponse> {
  const res = await api.post<TokenResponse>("/auth/register", {
    username,
    password,
  });
  return res.data;
}

export async function login(
  username: string,
  password: string
): Promise<TokenResponse> {
  const res = await api.post<TokenResponse>("/auth/token", {
    username,
    password,
  });
  return res.data;
}

export async function listConversations(
  token: string
): Promise<ConversationSummary[]> {
  const res = await api.get<ConversationSummary[]>("/conversations", {
    headers: { Authorization: `Bearer ${token}` },
  });
  return res.data;
}

export async function getConversation(
  token: string,
  conversationId: string
): Promise<ConversationDetail> {
  const res = await api.get<ConversationDetail>(
    `/conversations/${conversationId}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return res.data;
}

export function buildWebSocketUrl(
  token: string,
  conversationId?: string
): string {
  const base = `ws://localhost:8000/chat/ws?token=${token}`;
  return conversationId ? `${base}&conversation_id=${conversationId}` : base;
}