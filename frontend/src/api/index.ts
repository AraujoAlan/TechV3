/**
 * Camada de API — tudo que fala com o backend mora aqui.
 * A pasta `ui/` nunca deve importar `fetch` diretamente.
 */
export { streamChat } from './chat'
export { checkHealth } from './health'
export type { BackendStatus } from './health'
export { ApiError, toUserMessage } from './errors'
export { USE_MOCK, ENDPOINTS, BASE_URL } from './config'
export type {
  ChatRequest,
  Message,
  Role,
  Source,
  StreamEvent,
  ToolCall,
} from './types'
