/**
 * Contrato compartilhado entre o frontend e a API do assistente médico.
 *
 * O backend (FastAPI + LangGraph) expõe `POST /api/chat` com resposta JSON
 * síncrona já validada. Não há streaming de tokens nem trilha interna de nós.
 */

export type Role = 'user' | 'assistant'

export type ChatOutcome = 'completed' | 'limited'

/** Origem citada pelo assistente — atende ao requisito de explainability. */
export interface Source {
  id: string
  /** Ex.: "Prontuário sintético" */
  title: string
  /** Trecho literal usado na resposta. */
  snippet?: string | null
  /** Tipo da origem, para o ícone/rótulo na UI. */
  kind?: 'protocolo' | 'prontuario' | 'exame' | 'documento'
}

export interface AlertInfo {
  status: 'simulated_recorded'
}

export interface Message {
  id: string
  role: Role
  content: string
  createdAt: number
  /** Presente apenas em mensagens do assistente. */
  sources?: Source[]
  alert?: AlertInfo | null
  outcome?: ChatOutcome
  /** `true` enquanto a API ainda não respondeu. */
  streaming?: boolean
  error?: string
}

/** Corpo do `POST /api/chat`. */
export interface ChatRequest {
  question: string
  /** Correlação/auditoria apenas — não ativa memória conversacional. */
  conversation_id?: string
}

/** Resposta pública já validada do `POST /api/chat`. */
export interface ChatResponse {
  audit_id: string
  outcome: ChatOutcome
  answer: string
  sources: Source[]
  alert: AlertInfo | null
}
