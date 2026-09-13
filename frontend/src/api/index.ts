/**
 * Camada de API — tudo que fala com o backend mora aqui.
 * A pasta `ui/` nunca deve importar `fetch` diretamente.
 */
export { sendChat } from './chat'
export { checkHealth } from './health'
export type { BackendStatus } from './health'
export { ApiError, toUserMessage } from './errors'
export { USE_MOCK, ENDPOINTS, BASE_URL } from './config'
export type {
  AlertInfo,
  ChatOutcome,
  ChatRequest,
  ChatResponse,
  Message,
  Role,
  Source,
} from './types'
