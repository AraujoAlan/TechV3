import { ENDPOINTS, USE_MOCK } from './config'
import { ApiError } from './errors'
import { mockSendChat } from './mock'
import type { ChatRequest, ChatResponse } from './types'

/**
 * Envia a pergunta corrente e devolve a resposta JSON já validada.
 *
 * Com `VITE_USE_MOCK=true` usa o mock local com o mesmo `ChatResponse`.
 */
export async function sendChat(
  request: ChatRequest,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  if (USE_MOCK) {
    return mockSendChat(request, signal)
  }

  const response = await fetch(ENDPOINTS.chat, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(request),
    signal,
  })

  if (!response.ok) {
    throw new ApiError(await describeFailure(response), response.status)
  }

  const body: unknown = await response.json()
  if (!isChatResponse(body)) {
    throw new ApiError('A API respondeu com um formato inesperado.')
  }
  return body
}

function isChatResponse(value: unknown): value is ChatResponse {
  if (!value || typeof value !== 'object') return false
  const body = value as Record<string, unknown>
  return (
    typeof body.audit_id === 'string' &&
    (body.outcome === 'completed' || body.outcome === 'limited') &&
    typeof body.answer === 'string' &&
    Array.isArray(body.sources)
  )
}

/** Extrai a mensagem de erro do backend, com fallback no status HTTP. */
async function describeFailure(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object') {
      const detail = (body as Record<string, unknown>).detail ?? (body as Record<string, unknown>).message
      if (typeof detail === 'string' && detail.length > 0) return detail
    }
  } catch {
    // Corpo não era JSON.
  }
  return `A API respondeu ${response.status} ${response.statusText}.`
}
