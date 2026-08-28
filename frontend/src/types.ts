export type SourceType = 'vector' | 'sql' | 'web';

export interface Citation {
  type: SourceType;
  title: string;
  snippet: string;
  url?: string | null;
  score?: number | null;
  metadata?: Record<string, unknown>;
}

export interface Evaluation {
  faithfulness: number;
  relevance: number;
  correctness: number;
  confidence: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  confidence?: number;
  evaluation?: Evaluation;
  routedModels?: Record<string, string>;
  streaming?: boolean;
}

export interface ModelInfo {
  model: string;
  provider: string;
  free: boolean;
}

export interface ConfigResponse {
  default_model: string;
  active_providers: string[];
  routes: Record<string, string>;
  available_models: ModelInfo[];
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  task_overrides?: Record<string, string>;
}
