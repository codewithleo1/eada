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

export interface UploadResponse {
  file_id: string;
  original_filename: string;
  extension: string;
  row_count: number;
  columns: { name: string; dtype: string }[];
  sample: Record<string, unknown>[];
  message: string;
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

export async function uploadFile(
  token: string,
  file: File
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await api.post<UploadResponse>("/upload", formData, {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "multipart/form-data",
    },
  });
  return res.data;
}

export function buildWebSocketUrl(
  token: string,
  conversationId?: string,
  fileId?: string
): string {
  let url = `ws://localhost:8000/chat/ws?token=${token}`;
  if (conversationId) url += `&conversation_id=${conversationId}`;
  if (fileId) url += `&file_id=${fileId}`;
  return url;
}