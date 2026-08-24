/**
 * Contrato compartilhado entre o frontend e a API do assistente médico.
 *
 * O backend (FastAPI + LangChain/LangGraph) deve expor `POST /api/chat`
 * respondendo `text/event-stream`. Cada evento SSE carrega um JSON de
 * `StreamEvent` no campo `data`.
 */

export type Role = 'user' | 'assistant'

/** Origem citada pelo assistente — atende ao requisito de explainability. */
export interface Source {
  id: string
  /** Ex.: "Protocolo de Hipertensão — Cap. 3" */
  title: string
  /** Trecho literal usado na resposta. */
  snippet?: string
  /** Tipo da origem, para o ícone/rótulo na UI. */
  kind?: 'protocolo' | 'prontuario' | 'exame' | 'documento'
}

/** Uma execução de tool do agent LangGraph, exibida como trilha de auditoria. */
export interface ToolCall {
  id: string
  /** Nome da tool: `buscar_prontuario`, `consultar_protocolo`, ... */
  name: string
  input?: Record<string, unknown>
  output?: string
  status: 'running' | 'done' | 'error'
}

export interface Message {
  id: string
  role: Role
  content: string
  createdAt: number
  /** Presente apenas em mensagens do assistente. */
  sources?: Source[]
  toolCalls?: ToolCall[]
  /** `true` enquanto os tokens ainda estão chegando. */
  streaming?: boolean
  error?: string
}

/** Corpo do `POST /api/chat`. */
export interface ChatRequest {
  /** Histórico completo, em ordem cronológica. */
  messages: Array<{ role: Role; content: string }>
  /** Mantém a memória de conversa no backend entre requisições. */
  conversationId?: string
}

/**
 * Eventos emitidos pelo stream SSE. Mapeiam quase 1:1 com o
 * `astream_events` do LangGraph.
 */
export type StreamEvent =
  /** Fragmento de texto da resposta. */
  | { type: 'token'; content: string }
  /** O agent decidiu chamar uma tool. */
  | { type: 'tool_start'; id: string; name: string; input?: Record<string, unknown> }
  /** A tool retornou. */
  | { type: 'tool_end'; id: string; output: string }
  /** Fontes consultadas para montar a resposta. */
  | { type: 'sources'; sources: Source[] }
  /** Fim do turno. */
  | { type: 'done'; messageId?: string; conversationId?: string }
  /** Falha tratada pelo backend. */
  | { type: 'error'; message: string }
