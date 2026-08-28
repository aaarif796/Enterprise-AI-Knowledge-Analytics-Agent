import type { ChatRequest, ChatMessage, Citation, ConfigResponse, Evaluation } from '../types';

const API_BASE = import.meta.env.VITE_API_BASE ?? '';

export async function fetchConfig(): Promise<ConfigResponse> {
  const res = await fetch(`${API_BASE}/api/config`);
  if (!res.ok) throw new Error('Failed to load config');
  return res.json();
}

export async function sendChat(payload: ChatRequest): Promise<ChatMessage> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Chat request failed');
  const data = await res.json();
  return {
    role: 'assistant',
    content: data.answer,
    citations: data.citations as Citation[],
    confidence: data.confidence,
    evaluation: data.evaluation as Evaluation,
    routedModels: data.routed_models,
  };
}

export async function ingestDocument(text: string, sourceName: string): Promise<number> {
  const res = await fetch(`${API_BASE}/api/documents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document: text, source_name: sourceName }),
  });
  if (!res.ok) throw new Error('Ingest failed');
  const data = await res.json();
  return data.chunks_ingested as number;
}
